MODEL_PRICING = {
    # — OpenAI
    "gpt-5-mini": {
        "input_per_1k": 0.000125,
        "output_per_1k": 0.00100,
    },
    "gpt-4o-mini": {
        "input_per_1k": 0.000075,
        "output_per_1k": 0.00030,
    },
    "gpt-4.1-mini": {
        "input_per_1k": 0.00020,
        "output_per_1k": 0.00080,
    },

    # — Gemini (text)
    "gemini-2.5-pro": {
        "input_per_1k": 0.00125,
        "output_per_1k": 0.01000,
    },
    "gemini-2.5-flash": {
        "input_per_1k": 0.00030,
        "output_per_1k": 0.00250,
    },
    "gemini-2.5-flash-lite": {
        "input_per_1k": 0.00010,
        "output_per_1k": 0.00040,
    },

    # — Perplexity
    "sonar": {
        "input_per_1k": 0.001,
        "output_per_1k": 0.001,
    },
}

IMAGE_MODEL_PRICING = {
    # Gemini image generation
    "gemini-2.5-flash-image": {
        "price_per_image": 0.039,   # USD per image
    },
    "gemini-3-pro-image": {
        "price_per_image": 0.134,   # USD per image
    },
}


from decimal import Decimal
import tiktoken

def count_tokens(text: str, model: str) -> int:
    try:
        enc = tiktoken.encoding_for_model(model)
    except KeyError:
        # Fallback to cl100k_base for non-OpenAI models like 'sonar'
        enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


def calculate_llm_cost(model: str,input_tokens: int,output_tokens: int) -> Decimal:
    pricing = MODEL_PRICING[model]

    input_cost = (Decimal(input_tokens) / Decimal(1000)) * Decimal(pricing["input_per_1k"])
    output_cost = (Decimal(output_tokens) / Decimal(1000)) * Decimal(pricing["output_per_1k"])

    return (input_cost + output_cost).quantize(Decimal("0.000001"))


def calculate_image_cost(model: str,images_generated: int = 1) -> Decimal:
    pricing = IMAGE_MODEL_PRICING[model]
    return (Decimal(images_generated) * Decimal(pricing["price_per_image"])).quantize(
        Decimal("0.000001")
    )