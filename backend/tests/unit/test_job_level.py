from app.utils.job_level import infer_experience_years, infer_seniority


def test_infer_seniority_from_title() -> None:
    assert infer_seniority("Senior Python Developer") == "senior"
    assert infer_seniority("Junior Frontend Engineer") == "junior"
    assert infer_seniority("Mid-level Backend Engineer") == "mid"
    assert infer_seniority("Software Engineer") is None


def test_infer_experience_years_range() -> None:
    assert infer_experience_years("Requires 3-5 years of experience") == (3, 5)
    assert infer_experience_years("5+ years experience preferred") == (5, None)
    assert infer_experience_years("at least 2 years") == (2, None)
    assert infer_experience_years("No experience mentioned") == (None, None)
