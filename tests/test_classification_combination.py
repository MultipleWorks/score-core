"""Tests for R24 classification combination validation."""

from score.validator import validate_classification_combination


def test_valid_combinations_pass():
    valid = [
        ("public", "unrestricted"),
        ("internal", "unrestricted"),
        ("internal", "restricted"),
        ("confidential", "restricted"),
        ("confidential", "classified"),
        ("secret", "classified"),
    ]
    for cls, acc in valid:
        errors, warnings = validate_classification_combination(cls, acc)
        assert not errors, f"{cls}+{acc} should be valid, got errors: {errors}"


def test_invalid_combinations_error():
    invalid = [
        ("public", "restricted"),
        ("public", "classified"),
        ("confidential", "unrestricted"),
        ("secret", "unrestricted"),
        ("secret", "restricted"),
    ]
    for cls, acc in invalid:
        errors, _ = validate_classification_combination(cls, acc)
        assert errors, f"{cls}+{acc} should produce an error"


def test_internal_classified_is_warning_not_error():
    errors, warnings = validate_classification_combination("internal", "classified")
    assert not errors
    assert warnings
    assert "confidential" in warnings[0].lower()


def test_none_values_skip_validation():
    errors, warnings = validate_classification_combination(None, None)
    assert not errors
    assert not warnings


def test_partial_none_skips_validation():
    errors, warnings = validate_classification_combination("confidential", None)
    assert not errors
    assert not warnings


def test_public_restricted_error_message():
    errors, _ = validate_classification_combination("public", "restricted")
    assert "public" in errors[0].lower()
    assert "unrestricted" in errors[0].lower()


def test_secret_restricted_error_message():
    errors, _ = validate_classification_combination("secret", "restricted")
    assert "classified" in errors[0].lower()


def test_confidential_unrestricted_error_message():
    errors, _ = validate_classification_combination("confidential", "unrestricted")
    assert "confidential" in errors[0].lower()
