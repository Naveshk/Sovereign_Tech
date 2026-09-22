import ollama


def generate_response(model: str, prompt: str) -> str:

    response = ollama.chat(
        model=model,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    return response["message"]["content"]


def analyze_image(
    model: str,
    prompt: str,
    image_path: str
) -> str:

    response = ollama.chat(
        model=model,
        messages=[
            {
                "role": "user",
                "content": prompt,
                "images": [image_path]
            }
        ]
    )

    return response["message"]["content"]