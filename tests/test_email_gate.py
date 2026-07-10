"""Email gate validation logic (pure part)."""
import pytest

from app.email_gate import is_valid_email


@pytest.mark.parametrize("email", [
    "a@b.co", "carlos.salas@example.com", "x_y+tag@sub.domain.org", "UPPER@CASE.COM",
])
def test_valid_emails(email):
    assert is_valid_email(email)


@pytest.mark.parametrize("email", [
    "", "   ", "plainstring", "a@b", "@nouser.com", "user@.com",
    "user@domain", "user @space.com", "user@domain.c om", None,
])
def test_invalid_emails(email):
    assert not is_valid_email(email)


def test_strips_whitespace():
    assert is_valid_email("  a@b.co  ")
