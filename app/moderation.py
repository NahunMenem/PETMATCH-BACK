from fastapi import HTTPException, status


OBJECTIONABLE_TERMS = {
    "porno",
    "pornografia",
    "sexo",
    "violacion",
    "matar",
    "maltrato",
    "tortura",
    "droga",
    "cocaina",
    "arma",
    "estafa",
}


def validate_clean_text(*values: str | None) -> None:
    joined = " ".join(value or "" for value in values).lower()
    normalized = (
        joined.replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
    )
    if any(term in normalized for term in OBJECTIONABLE_TERMS):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El contenido contiene terminos no permitidos",
        )
