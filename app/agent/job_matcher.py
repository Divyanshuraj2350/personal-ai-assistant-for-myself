import re


# ============================================================
# NORMALIZATION
# ============================================================

def _normalize(text):
    if text is None:
        return ""

    text = str(text).lower()

    text = re.sub(
        r"[^a-z0-9+#./\- ]+",
        " ",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


# ============================================================
# PROFILE SKILLS
# ============================================================

def _flatten_profile_skills(profile):
    """
    Return skills explicitly declared in career_profile.json.

    No inference is performed here.
    """

    skills = set()

    profile_skills = profile.get(
        "skills",
        {},
    )

    if not isinstance(
        profile_skills,
        dict,
    ):
        return skills

    for values in profile_skills.values():

        if not isinstance(
            values,
            list,
        ):
            continue

        for value in values:

            normalized = _normalize(
                value
            )

            if normalized:
                skills.add(
                    normalized
                )

    return skills


# ============================================================
# PROFILE EXPERIENCE / PROJECT EVIDENCE
# ============================================================

def _collect_profile_evidence(profile):
    """
    Collect explicit text from experience and projects.

    This is used as evidence for a requirement.

    It does NOT create new skills.
    """

    evidence = []

    # -----------------------------
    # Experience
    # -----------------------------

    for experience in profile.get(
        "experience",
        [],
    ):

        if not isinstance(
            experience,
            dict,
        ):
            continue

        role = experience.get(
            "role"
        )

        if role:
            evidence.append(
                str(role)
            )

        responsibilities = experience.get(
            "responsibilities",
            [],
        )

        if isinstance(
            responsibilities,
            list,
        ):
            evidence.extend(
                str(item)
                for item in responsibilities
                if item
            )

    # -----------------------------
    # Projects
    # -----------------------------

    for project in profile.get(
        "projects",
        [],
    ):

        if not isinstance(
            project,
            dict,
        ):
            continue

        name = project.get(
            "name"
        )

        if name:
            evidence.append(
                str(name)
            )

        description = project.get(
            "description"
        )

        if description:
            evidence.append(
                str(description)
            )

        technologies = project.get(
            "technologies",
            [],
        )

        if isinstance(
            technologies,
            list,
        ):
            evidence.extend(
                str(item)
                for item in technologies
                if item
            )

    return [
        _normalize(item)
        for item in evidence
        if item
    ]


# ============================================================
# PROFILE SKILL ALIASES
# ============================================================

SKILL_ALIASES = {

    "python": {
        "python",
    },

    "c++": {
        "c++",
        "cpp",
    },

    "javascript": {
        "javascript",
        "js",
    },

    "react.js": {
        "react.js",
        "react",
    },

    "node.js": {
        "node.js",
        "node",
    },

    "scikit-learn": {
        "scikit-learn",
        "sklearn",
    },

    "mysql": {
        "mysql",
    },

    "mongodb": {
        "mongodb",
        "mongo",
    },

    "computer vision": {
        "computer vision",
    },

    "fastapi": {
        "fastapi",
    },

    "solidity": {
        "solidity",
    },

    "ethereum": {
        "ethereum",
    },

    "smart contracts": {
        "smart contract",
        "smart contracts",
    },

    "html": {
        "html",
    },

    "css": {
        "css",
    },

    "git": {
        "git",
    },

    "github": {
        "github",
    },

    "linux/ubuntu": {
        "linux",
        "ubuntu",
        "linux/ubuntu",
    },

    "bash scripting": {
        "bash",
        "bash scripting",
    },

    "rest apis": {
        "rest",
        "rest api",
        "rest apis",
    },

    "python ml pipelines": {
        "python ml pipelines",
    },

    "llm apis": {
        "llm apis",
    },

    "openai apis": {
        "openai api",
        "openai apis",
    },

    "tcp/ip": {
        "tcp/ip",
        "tcp",
        "ip",
    },
}


# ============================================================
# RELATED SKILLS
# ============================================================

RELATED_SKILLS = {

    # MySQL is evidence of SQL experience, but not an exact
    # replacement for a generic SQL requirement.
    "sql": {
        "mysql",
    },

    "machine learning": {
        "python ml pipelines",
        "scikit-learn",
    },

    "ml": {
        "python ml pipelines",
        "scikit-learn",
    },

    "rest": {
        "rest apis",
    },

    "rest api": {
        "rest apis",
    },

    "rest apis": {
        "rest apis",
    },
}


# ============================================================
# JOB REQUIREMENT CONCEPT EXTRACTION
# ============================================================

def _extract_requirement_concepts(
    requirement
):
    """
    Convert a natural-language requirement into important
    technical/conceptual terms.

    The original requirement is preserved separately.

    Example:

        "Strong programming ability in Python"

    becomes:

        ["python"]

    Example:

        "Hands-on experience creating and assessing
         machine learning models"

    becomes:

        ["machine learning"]
    """

    text = _normalize(
        requirement
    )

    concepts = []

    known_terms = [

        "python",
        "c++",
        "java",
        "javascript",

        "machine learning",
        "deep learning",
        "computer vision",

        "scikit-learn",
        "sklearn",

        "sql",
        "mysql",
        "mongodb",

        "fastapi",
        "react",
        "react.js",
        "node",
        "node.js",

        "apache spark",
        "spark",
        "databricks",
        "azure databricks",
        "azure",

        "xgboost",
        "lightgbm",

        "time-series",
        "time series",

        "etl",
        "etl processes",

        "data engineering",

        "tensorflow",
        "pytorch",

        "aws",
        "gcp",

        "docker",
        "kubernetes",

        "rest",
        "rest api",
        "rest apis",

        "git",
        "github",

        "linux",
        "ubuntu",
        "bash",

        "solidity",
        "ethereum",

        "smart contracts",
    ]

    known_terms.sort(
        key=len,
        reverse=True,
    )

    for term in known_terms:

        normalized_term = _normalize(
            term
        )

        if not normalized_term:
            continue

        pattern = (
            r"(?<![a-z0-9])"
            + re.escape(normalized_term)
            + r"(?![a-z0-9])"
        )

        if re.search(
            pattern,
            text,
        ):

            if normalized_term not in concepts:
                concepts.append(
                    normalized_term
                )

    return concepts


# ============================================================
# DIRECT SKILL MATCH
# ============================================================

def _skill_matches_explicitly(
    job_skill,
    profile_skills,
):
    """
    Exact match against explicitly declared profile skills.

    No broad profile-text matching occurs here.
    """

    normalized_job_skill = _normalize(
        job_skill
    )

    if not normalized_job_skill:
        return False, None

    # Exact skill.
    if normalized_job_skill in profile_skills:
        return (
            True,
            normalized_job_skill,
        )

    # Alias matching.
    for profile_skill in profile_skills:

        aliases = SKILL_ALIASES.get(
            profile_skill,
            {profile_skill},
        )

        normalized_aliases = {
            _normalize(alias)
            for alias in aliases
        }

        if normalized_job_skill in normalized_aliases:

            return (
                True,
                profile_skill,
            )

    return (
        False,
        None,
    )


# ============================================================
# RELATED SKILL MATCH
# ============================================================

def _find_related_skill(
    job_skill,
    profile_skills,
):
    """
    Find a conservative related skill.

    Related is deliberately different from exact.
    """

    normalized_job_skill = _normalize(
        job_skill
    )

    candidates = RELATED_SKILLS.get(
        normalized_job_skill,
        set(),
    )

    for candidate in candidates:

        if candidate in profile_skills:

            return candidate

    return None


# ============================================================
# EVIDENCE SIGNALS
# ============================================================

EVIDENCE_SIGNALS = {

    # A job can describe ML work using several different
    # phrases. These signals are evidence only; they do not
    # create a new explicit profile skill.
    "machine learning": {
        "machine learning",
        "ml model",
        "ml models",
        "predictive model",
        "predictive models",
        "prediction model",
        "prediction models",
        "trained ml",
        "trained models",
        "trained and evaluated",
        "model training",
        "model development",
    },

    "predictive analytics": {
        "predictive analytics",
        "predictive model",
        "predictive models",
        "prediction model",
        "prediction models",
        "machine failure prediction",
        "failure prediction",
        "forecasting",
        "prediction",
    },

    "model evaluation": {
        "model evaluation",
        "model testing",
        "evaluated",
        "evaluating",
        "assessed",
        "assessment",
        "accuracy",
        "roc-auc",
        "roc auc",
        "performance metrics",
        "model performance",
    },

    "python": {
        "python",
    },

    "sql": {
        "sql",
    },

    "data preprocessing": {
        "preprocessing",
        "data preprocessing",
        "data preparation",
        "preprocessed",
        "preprocess",
    },

    "model deployment": {
        "model deployment",
        "deployment workflow",
        "production ml",
        "production machine learning",
        "model deployment workflows",
    },

    "feature analysis": {
        "feature importance",
        "feature analysis",
        "feature engineering",
        "feature inputs",
    },

    "computer vision": {
        "computer vision",
        "facial recognition",
        "face recognition",
    },

    "llm": {
        "llm",
        "llm api",
        "llm apis",
        "gemini ai",
        "qwen3",
        "language model",
    },

    "rag": {
        "rag",
        "retrieval augmented",
        "vector-based retrieval",
        "vector based retrieval",
    },
}


# ============================================================
# EVIDENCE MATCH
# ============================================================

def _find_evidence_for_concept(
    concept,
    profile_evidence,
):
    """
    Find explicit experience/project evidence for a job
    concept.

    Evidence matching is intentionally separate from direct
    skill matching.

    Example:

        Job requirement:
            "machine learning models"

        Profile evidence:
            "Built a machine failure prediction model..."

    This can be treated as evidence for machine learning.

    Important:

        Evidence does NOT mean the candidate automatically
        possesses every technology mentioned by the job.

    For example, evidence for machine learning does NOT mean:

        Databricks
        Spark
        Azure
        XGBoost
        LightGBM

    are possessed.
    """

    normalized_concept = _normalize(
        concept
    )

    if not normalized_concept:
        return None

    # --------------------------------------------------------
    # Determine acceptable evidence signals.
    #
    # Exact concept first.
    # --------------------------------------------------------

    signals = set()

    if normalized_concept in EVIDENCE_SIGNALS:

        signals.update(
            EVIDENCE_SIGNALS[
                normalized_concept
            ]
        )

    else:

        signals.add(
            normalized_concept
        )

    # Longest signals first to avoid unnecessary short matches.
    signals = sorted(
        signals,
        key=len,
        reverse=True,
    )

    for evidence in profile_evidence:

        normalized_evidence = _normalize(
            evidence
        )

        if not normalized_evidence:
            continue

        for signal in signals:

            normalized_signal = _normalize(
                signal
            )

            if not normalized_signal:
                continue

            pattern = (
                r"(?<![a-z0-9])"
                + re.escape(
                    normalized_signal
                )
                + r"(?![a-z0-9])"
            )

            if re.search(
                pattern,
                normalized_evidence,
            ):

                return evidence

    return None


# ============================================================
# LIST CLEANING
# ============================================================

def _clean_list(values):

    if not isinstance(
        values,
        list,
    ):
        return []

    result = []

    for value in values:

        if value is None:
            continue

        value = str(value).strip()

        if not value:
            continue

        if value not in result:
            result.append(
                value
            )

    return result


# ============================================================
# REQUIRED SKILL ANALYSIS
# ============================================================

def _analyze_requirement(
    requirement,
    profile_skills,
    profile_evidence,
):
    """
    Analyze one natural-language job requirement.

    Returns:

        exact matches
        evidence matches
        related matches
        missing concepts
    """

    concepts = _extract_requirement_concepts(
        requirement
    )

    result = {
        "requirement": requirement,
        "matched": [],
        "evidence": [],
        "related": [],
        "missing": [],
    }

    # If no technical concept was extracted, do not blindly
    # classify the requirement as a missing skill.
    if not concepts:

        return result

    for concept in concepts:

        exact, profile_skill = (
            _skill_matches_explicitly(
                concept,
                profile_skills,
            )
        )

        if exact:

            result["matched"].append(
                {
                    "job_skill": concept,
                    "profile_skill": profile_skill,
                }
            )

            continue

        related = _find_related_skill(
            concept,
            profile_skills,
        )

        if related:

            result["related"].append(
                {
                    "job_skill": concept,
                    "profile_skill": related,
                }
            )

            continue

        evidence = _find_evidence_for_concept(
            concept,
            profile_evidence,
        )

        if evidence:

            result["evidence"].append(
                {
                    "concept": concept,
                    "evidence": evidence,
                }
            )

            continue

        result["missing"].append(
            concept
        )

    return result


# ============================================================
# SKILL SCORE
# ============================================================

def _calculate_skill_score(
    job,
    profile,
):

    profile_skills = _flatten_profile_skills(
        profile
    )

    profile_evidence = _collect_profile_evidence(
        profile
    )

    required = _clean_list(
        job.get(
            "required_skills",
            [],
        )
    )

    preferred = _clean_list(
        job.get(
            "preferred_skills",
            [],
        )
    )

    tech_stack = _clean_list(
        job.get(
            "tech_stack",
            [],
        )
    )

    # --------------------------------------------------------
    # Required requirements
    # --------------------------------------------------------

    required_analysis = []

    for requirement in required:

        analysis = _analyze_requirement(
            requirement,
            profile_skills,
            profile_evidence,
        )

        required_analysis.append(
            analysis
        )

    # --------------------------------------------------------
    # Preferred requirements
    # --------------------------------------------------------

    preferred_analysis = []

    for requirement in preferred:

        analysis = _analyze_requirement(
            requirement,
            profile_skills,
            profile_evidence,
        )

        preferred_analysis.append(
            analysis
        )

    # --------------------------------------------------------
    # Tech stack
    # --------------------------------------------------------

    matched_tech = []
    related_tech = []
    missing_tech = []

    for technology in tech_stack:

        exact, profile_skill = (
            _skill_matches_explicitly(
                technology,
                profile_skills,
            )
        )

        if exact:

            matched_tech.append(
                {
                    "job_skill": technology,
                    "profile_skill": profile_skill,
                }
            )

            continue

        related = _find_related_skill(
            technology,
            profile_skills,
        )

        if related:

            related_tech.append(
                {
                    "job_skill": technology,
                    "profile_skill": related,
                }
            )

            continue

        missing_tech.append(
            technology
        )

    # --------------------------------------------------------
    # Flatten required results
    # --------------------------------------------------------

    matched_required = []
    related_required = []
    evidence_required = []
    missing_required = []

    for analysis in required_analysis:

        matched_required.extend(
            analysis["matched"]
        )

        related_required.extend(
            analysis["related"]
        )

        evidence_required.extend(
            analysis["evidence"]
        )

        missing_required.extend(
            analysis["missing"]
        )

    # --------------------------------------------------------
    # Flatten preferred results
    # --------------------------------------------------------

    matched_preferred = []
    related_preferred = []
    evidence_preferred = []
    missing_preferred = []

    for analysis in preferred_analysis:

        matched_preferred.extend(
            analysis["matched"]
        )

        related_preferred.extend(
            analysis["related"]
        )

        evidence_preferred.extend(
            analysis["evidence"]
        )

        missing_preferred.extend(
            analysis["missing"]
        )

    # --------------------------------------------------------
    # Remove duplicate dictionaries
    # --------------------------------------------------------

    def unique_dicts(values):

        result = []
        seen = set()

        for item in values:

            key = str(
                sorted(
                    item.items()
                )
            )

            if key in seen:
                continue

            seen.add(key)

            result.append(
                item
            )

        return result

    matched_required = unique_dicts(
        matched_required
    )

    related_required = unique_dicts(
        related_required
    )

    evidence_required = unique_dicts(
        evidence_required
    )

    matched_preferred = unique_dicts(
        matched_preferred
    )

    related_preferred = unique_dicts(
        related_preferred
    )

    evidence_preferred = unique_dicts(
        evidence_preferred
    )

    missing_required = list(
        dict.fromkeys(
            missing_required
        )
    )

    missing_preferred = list(
        dict.fromkeys(
            missing_preferred
        )
    )

    # --------------------------------------------------------
    # Required skill score
    # --------------------------------------------------------

    required_concepts = 0
    required_points = 0.0

    for analysis in required_analysis:

        concepts = (
            _extract_requirement_concepts(
                analysis["requirement"]
            )
        )

        if not concepts:
            continue

        required_concepts += len(
            concepts
        )

        required_points += (
            len(analysis["matched"])
            + len(analysis["evidence"])
            + len(analysis["related"]) * 0.5
        )

    required_ratio = (
        required_points / required_concepts
        if required_concepts
        else 1.0
    )

    # --------------------------------------------------------
    # Preferred skill score
    # --------------------------------------------------------

    preferred_concepts = 0
    preferred_points = 0.0

    for analysis in preferred_analysis:

        concepts = (
            _extract_requirement_concepts(
                analysis["requirement"]
            )
        )

        if not concepts:
            continue

        preferred_concepts += len(
            concepts
        )

        preferred_points += (
            len(analysis["matched"])
            + len(analysis["evidence"])
            + len(analysis["related"]) * 0.5
        )

    preferred_ratio = (
        preferred_points / preferred_concepts
        if preferred_concepts
        else 1.0
    )

    # --------------------------------------------------------
    # Technology stack score
    # --------------------------------------------------------

    tech_points = (
        len(matched_tech)
        + len(related_tech) * 0.5
    )

    tech_ratio = (
        tech_points / len(tech_stack)
        if tech_stack
        else 0.0
    )

    # --------------------------------------------------------
    # Overall technical score
    # --------------------------------------------------------

    score = (
        required_ratio * 70
        + preferred_ratio * 20
        + tech_ratio * 10
    )

    return {

        "score": round(
            min(
                max(
                    score,
                    0,
                ),
                100,
            ),
            2,
        ),

        "matched_required": matched_required,

        "related_required": related_required,

        "evidence_required": evidence_required,

        "missing_required": missing_required,

        "matched_preferred": matched_preferred,

        "related_preferred": related_preferred,

        "evidence_preferred": evidence_preferred,

        "missing_preferred": missing_preferred,

        "matched_tech_stack": matched_tech,

        "related_tech_stack": related_tech,

        "missing_tech_stack": missing_tech,
    }


# ============================================================
# EXPERIENCE
# ============================================================

def _calculate_experience_match(
    job,
    profile,
):

    requirements = _clean_list(
        job.get(
            "experience",
            [],
        )
    )

    profile_experience = profile.get(
        "experience",
        []
    )

    if not requirements:
        return {
            "status": "not_specified",
            "score": 1.0,
            "job_requirements": [],
            "relevant_experience": [],
            "required_years": None,
            "candidate_years": None,
        }

    if not profile_experience:
        return {
            "status": "gap",
            "score": 0.0,
            "job_requirements": requirements,
            "relevant_experience": [],
            "required_years": None,
            "candidate_years": None,
        }

    combined = _normalize(
        " ".join(
            requirements
        )
    )

    # --------------------------------------------------------
    # Extract required years
    # --------------------------------------------------------

    year_match = re.search(
        r"(\d+)\s*\+?\s*(?:years?|yrs?)",
        combined,
    )

    required_years = None

    if year_match:
        required_years = int(
            year_match.group(1)
        )

    # --------------------------------------------------------
    # Build candidate experience text
    # --------------------------------------------------------

    experience_text = _normalize(
        " ".join(
            str(item)
            for item in profile_experience
        )
    )

    # --------------------------------------------------------
    # Detect relevant experience evidence
    # --------------------------------------------------------

    relevant_signals = [
        "machine learning",
        "machine learning model",
        "ml model",
        "predictive",
        "prediction",
        "data science",
        "data scientist",
        "python",
        "scikit learn",
        "model development",
        "model training",
        "model evaluation",
        "data preprocessing",
        "data analysis",
        "artificial intelligence",
        "ai",
    ]

    relevant_experience = []

    for signal in relevant_signals:

        if signal in experience_text:
            relevant_experience.append(
                signal
            )

    relevant_experience = _clean_list(
        relevant_experience
    )

    # --------------------------------------------------------
    # Estimate candidate years conservatively
    #
    # We do NOT invent years.
    # --------------------------------------------------------

    candidate_years = None

    # --------------------------------------------------------
    # Required years check
    # --------------------------------------------------------

    if required_years is not None:

        if candidate_years is not None:

            if candidate_years >= required_years:
                status = "match"
                score = 1.0

            elif candidate_years > 0:
                status = "partial_match"
                score = 0.5

            else:
                status = "gap"
                score = 0.0

        else:

            # We have relevant experience evidence,
            # but the profile does not establish enough
            # total years to satisfy the requirement.
            if relevant_experience:

                status = "partial_match"
                score = 0.5

            else:

                status = "gap"
                score = 0.0

    else:

        if relevant_experience:
            status = "match"
            score = 1.0
        else:
            status = "partial_match"
            score = 0.6

    return {
        "status": status,
        "score": score,
        "job_requirements": requirements,
        "relevant_experience": relevant_experience,
        "required_years": required_years,
        "candidate_years": candidate_years,
    }


# ============================================================
# EDUCATION
# ============================================================

def _calculate_education_match(
    job,
    profile,
):

    requirements = _clean_list(
        job.get(
            "education",
            [],
        )
    )

    education = profile.get(
        "education",
        []
    )

    if not requirements:
        return {
            "status": "not_specified",
            "score": 1.0,
            "requirements": [],
            "matched": [],
        }

    if not education:
        return {
            "status": "gap",
            "score": 0.0,
            "requirements": requirements,
            "matched": [],
        }

    matched = []

    # --------------------------------------------------------
    # Build normalized profile education text
    # --------------------------------------------------------

    education_text = _normalize(
        " ".join(
            " ".join(
                str(value)
                for value in item.values()
            )
            if isinstance(item, dict)
            else str(item)
            for item in education
        )
    )

    # --------------------------------------------------------
    # Education equivalence signals
    # --------------------------------------------------------

    bachelor_signals = {
        "bachelor",
        "bachelors",
        "bachelor degree",
        "bachelor of engineering",
        "bachelor of technology",
        "bachelor of science",
        "bachelor of computer science",
        "be",
        "b e",
        "btech",
        "b tech",
        "bsc",
        "b sc",
    }

    master_signals = {
        "master",
        "masters",
        "master degree",
        "master of engineering",
        "master of technology",
        "master of science",
        "me",
        "m e",
        "mtech",
        "m tech",
        "msc",
        "m sc",
    }

    phd_signals = {
        "phd",
        "doctorate",
        "doctoral",
    }

    # --------------------------------------------------------
    # Check each job education requirement
    # --------------------------------------------------------

    for requirement in requirements:

        normalized = _normalize(
            requirement
        )

        # Direct textual match
        if normalized in education_text:
            matched.append(requirement)
            continue

        # ----------------------------------------------------
        # Bachelor's requirement
        # ----------------------------------------------------

        if (
            "bachelor" in normalized
            or normalized in {
                "be",
                "b e",
                "btech",
                "b tech",
                "bsc",
                "b sc",
            }
        ):

            if any(
                signal in education_text
                for signal in bachelor_signals
            ):
                matched.append(requirement)
                continue

        # ----------------------------------------------------
        # Master's requirement
        # ----------------------------------------------------

        if (
            "master" in normalized
            or normalized in {
                "me",
                "m e",
                "mtech",
                "m tech",
                "msc",
                "m sc",
            }
        ):

            if any(
                signal in education_text
                for signal in master_signals
            ):
                matched.append(requirement)
                continue

        # ----------------------------------------------------
        # PhD requirement
        # ----------------------------------------------------

        if (
            "phd" in normalized
            or "doctorate" in normalized
            or "doctoral" in normalized
        ):

            if any(
                signal in education_text
                for signal in phd_signals
            ):
                matched.append(requirement)
                continue

    # --------------------------------------------------------
    # Final result
    # --------------------------------------------------------

    if len(matched) == len(requirements):
        return {
            "status": "match",
            "score": 1.0,
            "requirements": requirements,
            "matched": matched,
        }

    if matched:
        return {
            "status": "partial_match",
            "score": 0.5,
            "requirements": requirements,
            "matched": matched,
        }

    return {
        "status": "gap",
        "score": 0.0,
        "requirements": requirements,
        "matched": [],
    }


# ============================================================
# WORK MODE
# ============================================================

def _calculate_work_mode_match(
    job,
    profile,
):

    job_mode = _normalize(
        job.get(
            "work_mode"
        )
    )

    preferences = profile.get(
        "preferences",
        {},
    )

    if not job_mode:

        return {
            "status": "not_specified",
            "score": 1.0,
        }

    if not isinstance(
        preferences,
        dict,
    ):

        return {
            "status": "unknown",
            "score": 0.5,
        }

    if job_mode in {
        "remote",
        "hybrid",
        "onsite",
    }:

        if preferences.get(
            job_mode,
            False,
        ):

            return {
                "status": "match",
                "score": 1.0,
            }

        return {
            "status": "preference_mismatch",
            "score": 0.0,
        }

    return {
        "status": "unknown",
        "score": 0.5,
    }


# ============================================================
# LOCATION
# ============================================================

def _calculate_location_match(
    job,
    profile,
):

    job_location = _normalize(
        job.get(
            "location"
        )
    )

    preferred_locations = profile.get(
        "preferred_locations",
        [],
    )

    if not job_location:

        return {
            "status": "not_specified",
            "score": 1.0,
        }

    if not isinstance(
        preferred_locations,
        list,
    ):

        return {
            "status": "unknown",
            "score": 0.5,
        }

    preferences = [
        _normalize(value)
        for value in preferred_locations
        if value
    ]

    if "anywhere" in preferences:

        return {
            "status": "match",
            "score": 1.0,
        }

    for location in preferences:

        if (
            location in job_location
            or job_location in location
        ):

            return {
                "status": "match",
                "score": 1.0,
            }

    return {
        "status": "preference_mismatch",
        "score": 0.5,
    }


# ============================================================
# RECOMMENDATION
# ============================================================

def _recommendation(score):

    if score >= 80:
        return "strong_match"

    if score >= 65:
        return "good_match"

    if score >= 50:
        return "moderate_match"

    if score >= 35:
        return "weak_match"

    return "poor_match"


# ============================================================
# MAIN MATCHER
# ============================================================

def match_job_to_profile(
    job,
    profile,
):
    """
    Match an analyzed job against the career profile.

    Important:

        exact match
        related match
        evidence match
        missing requirement

    are kept separate.

    The matcher never converts a missing skill into a
    possessed skill.
    """

    if not isinstance(
        job,
        dict,
    ):
        raise ValueError(
            "job must be a dictionary."
        )

    if not isinstance(
        profile,
        dict,
    ):
        raise ValueError(
            "profile must be a dictionary."
        )

    skill_result = _calculate_skill_score(
        job,
        profile,
    )

    experience_result = _calculate_experience_match(
        job,
        profile,
    )

    education_result = _calculate_education_match(
        job,
        profile,
    )

    work_mode_result = _calculate_work_mode_match(
        job,
        profile,
    )

    location_result = _calculate_location_match(
        job,
        profile,
    )

    # --------------------------------------------------------
    # Overall score
    # --------------------------------------------------------

    score = (
        skill_result["score"] * 0.65
        + experience_result["score"] * 100 * 0.15
        + education_result["score"] * 100 * 0.05
        + work_mode_result["score"] * 100 * 0.10
        + location_result["score"] * 100 * 0.05
    )

    score = round(
        min(
            max(
                score,
                0,
            ),
            100,
        ),
        2,
    )

    # --------------------------------------------------------
    # Strengths
    # --------------------------------------------------------

    strengths = []

    if skill_result["matched_required"]:

        strengths.append(
            {
                "type": "required_skill",
                "items": skill_result[
                    "matched_required"
                ],
            }
        )

    # Use the dedicated experience matcher here.
    # This contains actual relevant experience evidence.
    if experience_result.get(
        "relevant_experience"
    ):

        strengths.append(
            {
                "type": "experience_evidence",
                "items": experience_result[
                    "relevant_experience"
                ],
            }
        )

    if skill_result["related_required"]:

        strengths.append(
            {
                "type": "related_skill",
                "items": skill_result[
                    "related_required"
                ],
            }
        )

    if skill_result["matched_tech_stack"]:

        strengths.append(
            {
                "type": "technology",
                "items": skill_result[
                    "matched_tech_stack"
                ],
            }
        )

    # --------------------------------------------------------
    # Gaps
    # --------------------------------------------------------

    gaps = []

    if skill_result["missing_required"]:

        gaps.append(
            {
                "type": "missing_required_skill",
                "items": skill_result[
                    "missing_required"
                ],
            }
        )

    if skill_result["missing_tech_stack"]:

        gaps.append(
            {
                "type": "missing_technology",
                "items": skill_result[
                    "missing_tech_stack"
                ],
            }
        )

    if skill_result["missing_preferred"]:

        gaps.append(
            {
                "type": "missing_preferred_skill",
                "items": skill_result[
                    "missing_preferred"
                ],
            }
        )

    # A partial match means relevant experience exists,
    # but the candidate does not fully satisfy the requirement.
    if experience_result["status"] == "gap":

        gaps.append(
            {
                "type": "experience",
                "details": (
                    "The profile does not provide "
                    "enough evidence for the explicit "
                    "experience requirement."
                ),
            }
        )

    elif experience_result["status"] == "partial_match":

        if experience_result.get(
            "required_years"
        ) is not None:

            gaps.append(
                {
                    "type": "experience",
                    "details": (
                        "The profile shows relevant "
                        "experience, but does not establish "
                        "the required number of years."
                    ),
                }
            )

    if education_result["status"] == "gap":

        gaps.append(
            {
                "type": "education",
                "details": (
                    "The explicit education requirement "
                    "is not supported by the profile."
                ),
            }
        )

    if work_mode_result["status"] == "preference_mismatch":

        gaps.append(
            {
                "type": "work_mode",
                "details": (
                    "The job work mode does not match "
                    "the current profile preference."
                ),
            }
        )

    if location_result["status"] == "preference_mismatch":

        gaps.append(
            {
                "type": "location",
                "details": (
                    "The job location does not match "
                    "the current preferred locations."
                ),
            }
        )

    # --------------------------------------------------------
    # Final result
    # --------------------------------------------------------

    return {

        "status": "success",

        "match_score": score,

        "recommendation": _recommendation(
            score
        ),

        "matched_skills": skill_result[
            "matched_required"
        ],

        "related_skills": skill_result[
            "related_required"
        ],

        # IMPORTANT:
        # Experience evidence comes from the dedicated
        # experience matcher, not skill_result.
        "experience_evidence": experience_result.get(
            "relevant_experience",
            []
        ),

        "missing_skills": skill_result[
            "missing_required"
        ],

        "preferred_skill_matches": skill_result[
            "matched_preferred"
        ],

        "missing_preferred_skills": skill_result[
            "missing_preferred"
        ],

        "matched_technologies": skill_result[
            "matched_tech_stack"
        ],

        "related_technologies": skill_result[
            "related_tech_stack"
        ],

        "missing_technologies": skill_result[
            "missing_tech_stack"
        ],

        "experience_match": experience_result,

        "education_match": education_result,

        "work_mode_match": work_mode_result,

        "location_match": location_result,

        "strengths": strengths,

        "gaps": gaps,
    }