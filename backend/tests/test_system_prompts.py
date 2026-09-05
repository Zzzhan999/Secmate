import pytest

from app.prompts.system_prompts import DISCLAIMER, SYSTEM_PROMPTS

SCENES = ["general", "http", "error", "code", "ctf", "linux", "protocol"]
SECTIONS = ["问题分析", "技术原理解释", "学习方向", "排查思路", "修复建议", "相关知识点", "推荐练习环境"]


@pytest.mark.parametrize("scene", SCENES)
def test_every_scene_has_seven_sections(scene):
    prompt = SYSTEM_PROMPTS[scene]
    for section in SECTIONS:
        assert section in prompt, f"{scene} 缺少段落: {section}"


@pytest.mark.parametrize("scene", SCENES)
def test_every_scene_has_safety_red_lines(scene):
    assert "授权" in SYSTEM_PROMPTS[scene]


def test_disclaimer_mentions_authorized_learning():
    assert "授权环境" in DISCLAIMER
