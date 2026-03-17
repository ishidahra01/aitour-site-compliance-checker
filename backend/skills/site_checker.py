"""
Site Checker Skill.

Points the Copilot SDK session to the site-checker skill directory.
"""
import os

#: Absolute path to the parent directory containing the site-checker skill subdirectory.
SITE_CHECKER_SKILLS_DIR: str = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "checker-skills"
)
