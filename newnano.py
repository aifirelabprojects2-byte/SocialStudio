from io import BytesIO
from google import genai
from google.genai import types
from PIL import Image
import os
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

image_path = "static/media/af1eb3f9-ec55-43c9-96a1-098c42678dfe_original.jpg"  
customization_text = "instead black use white backgroud and add aifirelab watermark"  
output_path = "edited_image.png"  

input_image = Image.open(image_path)

model_name = "gemini-2.5-flash-image"  # Or "gemini-3-pro-image-preview" 

response = client.models.generate_content(
    model=model_name,
    contents=[customization_text, input_image],
    config=types.GenerateContentConfig(
        response_modalities=["IMAGE"]  
    ),
)

# Extract and save the generated/edited image
for candidate in response.candidates:
    for part in candidate.content.parts:
        if part.inline_data is not None:
            image_data = part.inline_data.data
            edited_image = Image.open(BytesIO(image_data))
            edited_image.save(output_path)
            print(f"New edited image saved as {output_path}")
            break
    else:
        continue
    break
else:
    # If no image found, print any text response
    print("No image generated. Response text:")
    print(response.text)