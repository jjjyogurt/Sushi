import pytest

from app.utils.youtube import extract_video_id


@pytest.mark.parametrize(
    "input_value,expected",
    [
        ("dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ],
)
def test_extract_video_id(input_value, expected):
    assert extract_video_id(input_value) == expected


def test_extract_video_id_raises_for_invalid_input():
    with pytest.raises(ValueError):
        extract_video_id("https://example.com/not-youtube")

