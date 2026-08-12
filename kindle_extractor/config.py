from typing import Any, Dict


def get_default_config() -> Dict[str, Any]:
    return {
        "output_folder": "temp_output",
        "export_formats": {
            "markdown": {
                "enabled": True,
                "include_metadata": True,
                "folder": "markdown",
            },
            "html": {
                "enabled": True,
                "include_metadata": True,
                "css_style": "default",
                "folder": "html",
            },
            "txt": {
                "enabled": False,
                "include_metadata": False,
                "plain_text": True,
                "folder": "txt",
            },
            "obsidian": {
                "enabled": False,
                "include_metadata": True,
                "folder": "obsidian",
            },
        },
        "remove_duplicates": True,
        "similarity_threshold": 0.8,
        "dedup_position_overlap_ratio": 0.60,
        "dedup_token_overlap_threshold": 0.75,
        "dedup_session_window_minutes": 15,
        "dedup_prefix_words": 5,
        "include_bookmarks": True,
        "date_format": "portuguese",
        "encoding": "utf-8",
    }


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged
