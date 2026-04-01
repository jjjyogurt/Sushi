from __future__ import annotations

import csv
import io
import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.voc_evidence import VocEvidence
from app.models.voc_insight import VocInsight
from app.models.voc_row import VocRow
from app.repositories.voc_repository import (
    VocEvidenceRepository,
    VocInsightRepository,
    VocProjectRepository,
    VocReportRepository,
    VocRowRepository,
    VocRunRepository,
    VocSettingsRepository,
    VocUploadRepository,
)
from app.services.voc_policy import evaluate_publish_gate
from app.voc_defaults import DEFAULT_ANALYZER_SKILL_CONTENT, DEFAULT_CLEANER_SKILL_CONTENT


class VocService:
    METADATA_KEY_TOKENS = {
        "id",
        "ticket",
        "zendesk",
        "customer",
        "name",
        "channel",
        "order",
        "email",
        "e-mail",
        "mail",
        "phone",
        "product",
        "sku",
        "type",
        "category",
        "recommend",
        "一级分类",
        "二级分类",
        "三级分类",
        "用户原文",
    }
    CUSTOMER_TEXT_KEY_TOKENS = {
        "suggestion",
        "comment",
        "feedback",
        "message",
        "review",
        "request",
        "issue",
        "problem",
        "detail",
        "text",
        "body",
        "content",
        "description",
        "用户原文",
    }
    HEADER_TEXT_TOKENS = {
        "zendesk id",
        "customer name",
        "channel",
        "order id",
        "e-mail",
        "email",
        "product name",
        "product suggestion",
        "type",
        "recommend",
        "一级分类",
        "二级分类",
        "三级分类",
        "用户原文",
    }

    def __init__(self, session: Session):
        self.session = session
        self.projects = VocProjectRepository(session)
        self.uploads = VocUploadRepository(session)
        self.rows = VocRowRepository(session)
        self.runs = VocRunRepository(session)
        self.insights = VocInsightRepository(session)
        self.evidence = VocEvidenceRepository(session)
        self.reports = VocReportRepository(session)
        self.settings = VocSettingsRepository(session)

    def create_project(self, name: str, description: str):
        if not name.strip():
            raise ValueError("Project name is required.")
        return self.projects.create(name=name.strip(), description=description.strip())

    def list_projects(self):
        return self.projects.list_all()

    def get_project(self, project_id: int):
        project = self.projects.get(project_id)
        if project is None:
            raise ValueError("VOC project not found.")
        return project

    def update_project(self, project_id: int, name: str, description: str, status: str):
        project = self.get_project(project_id)
        return self.projects.update(project, name=name.strip(), description=description.strip(), status=status)

    def delete_project(self, project_id: int):
        project = self.get_project(project_id)
        self.projects.delete(project)

    def create_upload(self, project_id: int, filename: str, content: bytes):
        project = self.get_project(project_id)
        rows = self._parse_csv(content)
        upload = self.uploads.create(project_id=project.id, source_type="csv", filename=filename, total_rows=len(rows))
        row_models = [
            VocRow(
                upload_id=upload.id,
                row_index=index,
                raw_content=json.dumps(item, ensure_ascii=True),
            )
            for index, item in enumerate(rows, start=1)
        ]
        if row_models:
            self.rows.bulk_create(row_models)
        return upload

    def list_uploads(self, project_id: int):
        self.get_project(project_id)
        return self.uploads.list_by_project(project_id)

    def get_upload(self, upload_id: int):
        upload = self.uploads.get(upload_id)
        if upload is None:
            raise ValueError("VOC upload not found.")
        return upload

    def list_rows(self, upload_id: int, status: Optional[str], limit: int):
        self.get_upload(upload_id)
        return self.rows.list_by_upload(upload_id, status=status, limit=limit)

    def start_cleaning(self, upload_id: int):
        upload = self.get_upload(upload_id)
        cleaner_skill = self._ensure_default_skill("cleaner")
        run = self.runs.create(upload_id, "cleaning", total_rows=upload.total_rows, cleaner_skill_version_id=cleaner_skill.id)
        try:
            cleaned_count, failed_count = self._clean_rows(upload_id)
            self.runs.update_progress(run, cleaned_count, failed_count, status="completed")
            self.uploads.update_counts(upload, processed=cleaned_count, failed=failed_count, status="cleaned")
        except ValueError as error:
            self.runs.set_error(run, str(error))
            self.uploads.set_error(upload, str(error))
            self.runs.update_progress(run, run.processed_rows, run.failed_rows, status="failed")
            raise
        return run

    def start_analysis(self, upload_id: int):
        upload = self.get_upload(upload_id)
        analyzer_skill = self._ensure_default_skill("analyzer")
        self._ensure_default_skill("cleaner")
        run = self.runs.create(
            upload_id,
            "analysis",
            total_rows=upload.total_rows,
            analyzer_skill_version_id=analyzer_skill.id,
            report_template_version_id=None,
        )
        try:
            insights, buckets = self._analyze_rows(upload_id)
            report_content = self._build_report(upload.total_rows, insights, buckets)
            report = self.reports.create(
                project_id=upload.project_id,
                upload_id=upload.id,
                content=report_content,
                cleaner_skill_version_id=self._get_active_skill_id("cleaner"),
                analyzer_skill_version_id=analyzer_skill.id,
                report_template_version_id=None,
            )
            self.runs.update_progress(run, upload.total_rows, 0, status="completed")
            self.uploads.update_counts(upload, processed=upload.total_rows, failed=0, status="analyzed")
            return run, report
        except ValueError as error:
            self.runs.set_error(run, str(error))
            self.uploads.set_error(upload, str(error))
            self.runs.update_progress(run, run.processed_rows, run.failed_rows, status="failed")
            raise

    def get_report(self, project_id: int):
        self.get_project(project_id)
        report = self.reports.get_latest_by_project(project_id)
        if report is None:
            raise ValueError("VOC report not found.")
        return report

    def update_report(self, report_id: int, content: str):
        report = self.reports.get(report_id)
        if report is None:
            raise ValueError("VOC report not found.")
        return self.reports.update_content(report, content)

    def publish_report(self, report_id: int):
        report = self.reports.get(report_id)
        if report is None:
            raise ValueError("VOC report not found.")
        upload = self.get_upload(report.upload_id)
        gate = evaluate_publish_gate(upload.total_rows, upload.failed_rows, has_critical_failure=False)
        if not gate.allowed:
            self.reports.update_status(report, "draft", gate.reason)
        else:
            self.reports.update_status(report, "published", "")
        return gate, report

    def list_skill_versions(self, skill_type: str):
        self._ensure_default_skill(skill_type)
        return self.settings.list_skill_versions(skill_type)

    def create_skill_version(self, skill_type: str, name: str, content: str):
        return self.settings.create_skill_version(skill_type, name, content)

    def update_skill_version(self, version_id: int, name: str, content: str):
        version = self.settings.get_skill_version(version_id)
        if version is None:
            raise ValueError("VOC skill version not found.")
        return self.settings.update_skill_version(version, name, content)

    def validate_skill_version(self, version_id: int):
        version = self.settings.get_skill_version(version_id)
        if version is None:
            raise ValueError("VOC skill version not found.")
        return self.settings.set_skill_status(version, "validated")

    def activate_skill_version(self, version_id: int):
        version = self.settings.get_skill_version(version_id)
        if version is None:
            raise ValueError("VOC skill version not found.")
        if version.status != "validated":
            raise ValueError("Skill must be validated before activation.")
        return self.settings.activate_skill_version(version)

    def list_templates(self):
        self._ensure_default_template()
        return self.settings.list_templates()

    def create_template(self, name: str, content: str):
        return self.settings.create_template(name, content)

    def update_template(self, template_id: int, name: str, content: str):
        template = self.settings.get_template(template_id)
        if template is None:
            raise ValueError("VOC report template not found.")
        return self.settings.update_template(template, name, content)

    def preview_template(self, template_id: int):
        template = self.settings.get_template(template_id)
        if template is None:
            raise ValueError("VOC report template not found.")
        return self.settings.set_template_status(template, "preview")

    def activate_template(self, template_id: int):
        template = self.settings.get_template(template_id)
        if template is None:
            raise ValueError("VOC report template not found.")
        if template.status != "preview":
            raise ValueError("Template must be in preview before activation.")
        return self.settings.activate_template(template)

    def _parse_csv(self, content: bytes) -> List[Dict[str, str]]:
        if not content:
            raise ValueError("Uploaded file is empty.")
        try:
            decoded = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            decoded = content.decode("latin-1")
        buffer = io.StringIO(decoded)
        reader = csv.reader(buffer)
        rows = list(reader)
        if not rows:
            return []
        header = rows[0]
        if self._looks_like_header_row(header):
            fieldnames = [cell.strip() or f"col_{index + 1}" for index, cell in enumerate(header)]
            dict_reader = csv.DictReader(io.StringIO(decoded), fieldnames=fieldnames)
            next(dict_reader, None)
            return [dict(row) for row in dict_reader]
        return [self._row_to_dict(item) for item in rows]

    @staticmethod
    def _row_to_dict(row: List[str]) -> Dict[str, str]:
        return {f"col_{index + 1}": value for index, value in enumerate(row)}

    @classmethod
    def _looks_like_header_row(cls, row: List[str]) -> bool:
        if not row:
            return False
        normalized_cells = [cell.strip().lower() for cell in row if cell and cell.strip()]
        if not normalized_cells:
            return False
        keyword_hits = 0
        for cell in normalized_cells:
            if any(token in cell for token in cls.METADATA_KEY_TOKENS):
                keyword_hits += 1
        return keyword_hits >= max(2, len(normalized_cells) // 3)

    def _clean_rows(self, upload_id: int) -> Tuple[int, int]:
        rows = self.rows.list_all_by_upload(upload_id)
        processed = 0
        failed = 0
        for row in rows:
            try:
                raw = json.loads(row.raw_content) if row.raw_content else {}
                cleaned = self._clean_payload(raw)
                row.cleaned_content = json.dumps(cleaned, ensure_ascii=True)
                if cleaned.get("status") == "failed":
                    row.status = "failed"
                    row.error_message = str(cleaned.get("error_reason", "non_customer_text"))
                    failed += 1
                else:
                    row.status = "cleaned"
                    row.error_message = ""
                    processed += 1
            except (TypeError, ValueError) as error:
                row.status = "failed"
                row.error_message = str(error)
                failed += 1
            self.rows.save(row)
        return processed, failed

    def _analyze_rows(self, upload_id: int) -> Tuple[List[VocInsight], Dict[str, List[VocRow]]]:
        rows = self.rows.list_all_by_upload(upload_id)
        buckets: Dict[str, List[VocRow]] = {
            "value_drivers": [],
            "issues": [],
            "feature_desires": [],
            "competitors": [],
            "risks": [],
        }
        for row in rows:
            if row.status != "cleaned":
                continue
            payload = json.loads(row.cleaned_content or "{}")
            text = self._flatten_payload(payload)
            category, confidence = self._categorize_text(text)
            row.category = category
            row.confidence = confidence
            self.rows.save(row)
            if category in buckets:
                buckets[category].append(row)

        insights = []
        for category, category_rows in buckets.items():
            if not category_rows:
                continue
            insight = VocInsight(
                upload_id=upload_id,
                title=self._category_title(category),
                category=category,
                summary=f"{len(category_rows)} mentions identified.",
                confidence=self._confidence_from_rows(category_rows),
                severity=self._severity_for_category(category),
                owner=self._owner_for_category(category),
                team=self._team_for_category(category),
                recommended_action=self._recommended_action_for_category(category),
            )
            insights.append(insight)
        created_insights = self.insights.bulk_create(insights)
        evidence_items = self._build_evidence(created_insights, buckets)
        if evidence_items:
            self.evidence.bulk_create(evidence_items)
        return created_insights, buckets

    def _build_evidence(self, insights: List[VocInsight], buckets: Dict[str, List[VocRow]]) -> List[VocEvidence]:
        evidence_items: List[VocEvidence] = []
        for insight in insights:
            supporting_rows = buckets.get(insight.category, [])[:3]
            counterexample_rows = self._counterexample_rows(buckets, insight.category)[:1]
            for row in supporting_rows:
                evidence_items.append(
                    VocEvidence(
                        insight_id=insight.id,
                        row_id=row.id,
                        evidence_type="supporting",
                        snippet=row.cleaned_content,
                    )
                )
            for row in counterexample_rows:
                evidence_items.append(
                    VocEvidence(
                        insight_id=insight.id,
                        row_id=row.id,
                        evidence_type="counterexample",
                        snippet=row.cleaned_content,
                    )
                )
        return evidence_items

    @staticmethod
    def _counterexample_rows(buckets: Dict[str, List[VocRow]], target_category: str) -> List[VocRow]:
        for key, rows in buckets.items():
            if key != target_category and rows:
                return rows
        return []

    @staticmethod
    def _clean_payload(payload: Dict[str, Any]) -> Dict[str, str]:
        source = VocService._detect_source(payload)
        cleaned_text = VocService._extract_customer_text(payload)
        if not cleaned_text:
            return {
                "cleaned_text": "",
                "language": "unknown",
                "source": source,
                "status": "failed",
                "error_reason": "metadata_only",
            }
        if VocService._is_header_like_text(cleaned_text):
            return {
                "cleaned_text": "",
                "language": "unknown",
                "source": source,
                "status": "failed",
                "error_reason": "header_row",
            }
        language = VocService._detect_language(cleaned_text)
        return {
            "cleaned_text": cleaned_text,
            "language": language,
            "source": source,
            "status": "cleaned",
            "error_reason": "",
        }

    @staticmethod
    def _flatten_payload(payload: Dict[str, Any]) -> str:
        cleaned_text = str(payload.get("cleaned_text", "")).strip()
        if cleaned_text:
            return cleaned_text.lower()
        return " ".join(str(value) for value in payload.values()).lower()

    @classmethod
    def _extract_customer_text(cls, payload: Dict[str, Any]) -> str:
        if not payload:
            return ""
        scored_values: List[Tuple[int, str]] = []
        for key, value in payload.items():
            if not isinstance(value, str):
                continue
            text = cls._normalize_text(value)
            if not text:
                continue
            if cls._is_metadata_key(key):
                continue
            if cls._is_header_like_text(text):
                continue
            score = 1
            key_lower = key.strip().lower()
            if any(token in key_lower for token in cls.CUSTOMER_TEXT_KEY_TOKENS):
                score += 3
            if any(token in key_lower for token in cls.METADATA_KEY_TOKENS):
                score -= 2
            if len(text.split()) >= 4:
                score += 1
            scored_values.append((score, text))
        if not scored_values:
            return ""
        ordered = sorted(scored_values, key=lambda item: item[0], reverse=True)
        selected: List[str] = []
        for _, text in ordered:
            if text not in selected:
                selected.append(text)
            if len(selected) >= 2:
                break
        return cls._normalize_text(" ".join(selected))

    @classmethod
    def _is_metadata_key(cls, key: str) -> bool:
        normalized = key.strip().lower()
        if not normalized:
            return True
        if normalized.startswith("col_"):
            return False
        return any(token in normalized for token in cls.METADATA_KEY_TOKENS)

    @classmethod
    def _is_header_like_text(cls, text: str) -> bool:
        normalized = cls._normalize_text(text).lower()
        if not normalized:
            return True
        header_hits = sum(1 for token in cls.HEADER_TEXT_TOKENS if token in normalized)
        if header_hits >= 3:
            return True
        words = normalized.split()
        if len(words) <= 3:
            return False
        short_word_ratio = sum(1 for word in words if len(word) <= 3) / len(words)
        return short_word_ratio > 0.75 and header_hits >= 1

    @staticmethod
    def _normalize_text(text: str) -> str:
        collapsed = re.sub(r"\s+", " ", text).strip()
        redacted_email = re.sub(r"[\w\.-]+@[\w\.-]+", "[redacted]", collapsed)
        redacted_phone = re.sub(r"\b\+?\d[\d\s\-]{7,}\b", "[redacted]", redacted_email)
        no_urls = re.sub(r"https?://\S+", "[link]", redacted_phone)
        return VocService._strip_export_prefix(no_urls)

    @staticmethod
    def _strip_export_prefix(text: str) -> str:
        normalized = text.strip()
        lower = normalized.lower()
        if "product suggestion" in lower:
            _, _, suffix = normalized.partition("product suggestion")
            candidate = suffix.strip(" -:|/")
            if candidate:
                return candidate
        if "用户原文" in normalized:
            _, _, suffix = normalized.partition("用户原文")
            candidate = suffix.strip(" -:|/")
            if candidate:
                return candidate
        markers = [
            " any chance",
            " my suggestion",
            " it would",
            " i would",
            " i want",
            " i wish",
            " please",
            " could",
            " can ",
            " would ",
            " add ",
            " customer would like",
            " mine would",
            " mi permetto",
        ]
        if "[redacted]" in normalized or "unknown /" in lower or re.match(r"^\d{4,}\s", normalized):
            best_index = -1
            for marker in markers:
                index = lower.find(marker)
                if index != -1 and (best_index == -1 or index < best_index):
                    best_index = index
            if best_index > 0:
                return normalized[best_index:].strip(" -:|/")
        return normalized

    @staticmethod
    def _detect_language(text: str) -> str:
        if re.search(r"[\u4e00-\u9fff]", text):
            return "zh"
        if re.search(r"[a-zA-Z]", text):
            return "en"
        return "unknown"

    @staticmethod
    def _detect_source(payload: Dict[str, Any]) -> str:
        merged = " ".join(f"{key} {value}" for key, value in payload.items()).lower()
        if any(token in merged for token in ["zendesk", "ticket", "support"]):
            return "support_ticket"
        if any(token in merged for token in ["reddit", "r/"]):
            return "reddit"
        if any(token in merged for token in ["youtube", "yt", "video"]):
            return "youtube"
        if any(token in merged for token in ["app store", "play store"]):
            return "app_store"
        return "unknown"

    @staticmethod
    def _categorize_text(text: str) -> Tuple[str, float]:
        if any(token in text for token in ["competitor", "vs ", "compared to", "better than", "dji", "potensic"]):
            return "competitors", 0.84
        if any(
            token in text
            for token in ["churn", "refund", "return", "cancel", "unsafe", "danger", "trust", "expensive", "overpriced"]
        ):
            return "risks", 0.87
        if any(token in text for token in ["wish", "request", "feature", "add", "support", "would like", "missing"]):
            return "feature_desires", 0.78
        if any(token in text for token in ["crash", "broken", "issue", "problem", "bug", "bad", "drain", "drop"]):
            return "issues", 0.82
        if any(token in text for token in ["love", "great", "good", "excellent", "amazing", "easy", "fast", "portable"]):
            return "value_drivers", 0.8
        return "issues", 0.6

    @staticmethod
    def _confidence_from_rows(rows: List[VocRow]) -> float:
        if not rows:
            return 0.0
        total = sum(row.confidence for row in rows)
        return total / len(rows)

    def _build_report(self, total_rows: int, insights: List[VocInsight], buckets: Dict[str, List[VocRow]]) -> str:
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        ordered_categories = [
            "value_drivers",
            "issues",
            "feature_desires",
            "competitors",
            "risks",
        ]
        high_risk_count = sum(1 for item in insights if item.severity in {"high", "critical"})
        top_insights = sorted(
            insights,
            key=lambda item: (self._severity_rank(item.severity), item.confidence),
            reverse=True,
        )
        lines = [
            f"# VOC Report",
            "",
            f"Generated: {now}",
            "",
            "## Executive Summary",
            "- This report is generated directly by the VOC analyzer skill.",
            f"- Total records analyzed: {total_rows}",
            f"- Top insight count: {len(top_insights)}",
            f"- High / critical themes: {high_risk_count}",
            "",
            "## KPI Snapshot",
            "| Metric | Value | Why It Matters |",
            "|---|---:|---|",
            f"| Total records analyzed | {total_rows} | Shows coverage |",
            f"| Competitor mentions | {len(buckets['competitors'])} | Shows market pressure |",
            f"| High / critical themes | {high_risk_count} | Highlights urgent risk |",
            "",
            "## Top Insights",
            "| Priority | Insight | Bucket | Coverage | Severity | Confidence | Business Impact |",
            "|---|---|---|---:|---|---|---|",
        ]

        for index, insight in enumerate(top_insights, start=1):
            lines.append(
                "| {priority} | {title} | {bucket} | {coverage} | {severity} | {confidence} | {impact} |".format(
                    priority=index,
                    title=insight.title,
                    bucket=self._category_title(insight.category),
                    coverage=self._coverage_text(len(buckets.get(insight.category, [])), total_rows),
                    severity=insight.severity,
                    confidence=self._confidence_label(insight.confidence),
                    impact=insight.recommended_action,
                )
            )

        for category in ordered_categories:
            lines.extend(["", f"## {self._category_title(category)}"])
            category_rows = buckets.get(category, [])
            if not category_rows:
                lines.append("- No clear evidence found.")
                continue
            lines.append(
                f"- Coverage: {self._coverage_text(len(category_rows), total_rows)}"
            )
            lines.append(f"- Suggested owner: {self._owner_for_category(category)}")
            lines.append(f"- Recommended action: {self._recommended_action_for_category(category)}")
            lines.append("- Example signals:")
            for row in category_rows[:3]:
                lines.append(f"  - {self._snippet_from_row(row)}")

        lines.extend(
            [
                "",
                "## Recommended Actions",
                "| Action | Function | Urgency | Owner |",
                "|---|---|---|---|",
            ]
        )
        for category in ordered_categories:
            if not buckets.get(category):
                continue
            lines.append(
                "| {action} | {team} | {urgency} | {owner} |".format(
                    action=self._recommended_action_for_category(category),
                    team=self._team_for_category(category),
                    urgency=self._severity_for_category(category),
                    owner=self._owner_for_category(category),
                )
            )
        return "\n".join(lines)

    @staticmethod
    def _category_title(category: str) -> str:
        titles = {
            "value_drivers": "What Customers Value",
            "issues": "What Issues They Encounter",
            "feature_desires": "What They Wish Existed",
            "competitors": "Competitor and Market Signals",
            "risks": "Adoption, Retention, and Revenue Risks",
        }
        return titles.get(category, category.replace("_", " ").title())

    @staticmethod
    def _severity_for_category(category: str) -> str:
        severity = {
            "value_drivers": "medium",
            "issues": "high",
            "feature_desires": "medium",
            "competitors": "high",
            "risks": "critical",
        }
        return severity.get(category, "medium")

    @staticmethod
    def _owner_for_category(category: str) -> str:
        owners = {
            "value_drivers": "Product Marketing",
            "issues": "Product",
            "feature_desires": "Product",
            "competitors": "Product Marketing",
            "risks": "Leadership",
        }
        return owners.get(category, "Product")

    @staticmethod
    def _team_for_category(category: str) -> str:
        teams = {
            "value_drivers": "Marketing",
            "issues": "Engineering",
            "feature_desires": "Product",
            "competitors": "Marketing",
            "risks": "Leadership",
        }
        return teams.get(category, "Product")

    @staticmethod
    def _recommended_action_for_category(category: str) -> str:
        actions = {
            "value_drivers": "Reinforce proven value drivers in messaging and launch assets.",
            "issues": "Investigate root causes and reduce customer-facing friction.",
            "feature_desires": "Validate whether requests reflect a roadmap gap or an expectation gap.",
            "competitors": "Update positioning and track where competitor expectations are setting the bar.",
            "risks": "Escalate and assign an owner with a concrete mitigation plan.",
        }
        return actions.get(category, "Review and prioritize the theme.")

    @staticmethod
    def _confidence_label(confidence: float) -> str:
        if confidence >= 0.8:
            return "high"
        if confidence >= 0.6:
            return "medium"
        return "low"

    @staticmethod
    def _severity_rank(severity: str) -> int:
        ranks = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        return ranks.get(severity, 0)

    @staticmethod
    def _coverage_text(count: int, total_rows: int) -> str:
        if total_rows <= 0:
            return f"{count} mentions"
        percentage = round((count / total_rows) * 100, 1)
        return f"{count} mentions ({percentage}%)"

    def _snippet_from_row(self, row: VocRow) -> str:
        payload = json.loads(row.cleaned_content or "{}")
        snippet = str(payload.get("cleaned_text", "")).strip()
        if not snippet:
            snippet = self._flatten_payload(payload).replace("\n", " ").strip()
        return snippet[:160] if len(snippet) <= 160 else f"{snippet[:157]}..."

    def _ensure_default_skill(self, skill_type: str):
        versions = self.settings.list_skill_versions(skill_type)
        active = next((item for item in versions if item.is_active), None)
        if active:
            return active
        default_name = f"Default {skill_type.title()} Skill"
        if skill_type == "cleaner":
            default_content = DEFAULT_CLEANER_SKILL_CONTENT
        elif skill_type == "analyzer":
            default_content = DEFAULT_ANALYZER_SKILL_CONTENT
        else:
            default_content = (
                "Use best practices for VOC processing. Preserve evidence links and do not remove PII guardrails."
            )
        created = self.settings.create_skill_version(skill_type, default_name, default_content)
        self.settings.set_skill_status(created, "validated")
        return self.settings.activate_skill_version(created)

    def _ensure_default_template(self):
        templates = self.settings.list_templates()
        active = next((item for item in templates if item.is_active), None)
        if active:
            return active
        default_content = (
            "## VOC Report (Consumer Hardware)\n\n{{report_body}}\n\n## Critical Risks\n- TBD\n\n"
            "## Evidence and Counterexamples\n- TBD\n\n## Recommended Actions\n- TBD\n"
        )
        created = self.settings.create_template("Consumer Hardware Best Practice", default_content)
        self.settings.set_template_status(created, "preview")
        return self.settings.activate_template(created)

    def _get_active_skill_id(self, skill_type: str) -> Optional[int]:
        versions = self.settings.list_skill_versions(skill_type)
        active = next((item for item in versions if item.is_active), None)
        return active.id if active else None
