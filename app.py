import os
import sys

import gradio as gr
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

openai_key = os.getenv("OPENAI_API_KEY")

if openai_key == "<YOUR_OPENAI_API_KEY>":
    openai_key = ""

if openai_key == "":
    sys.exit("Please Provide Your OpenAI API Key")


def generate_image(text, model, quality, size):
    try:
        client = OpenAI(api_key=openai_key)

        response = client.images.generate(
            prompt=text,
            model="dall-e-2", # dall-e-2 or dall-e-3
            quality="standard", # standard or hd
            size="512x512", # varies for dalle-2 and dalle-3, see https://openai.com/pricing for resolutions
            n=1, # Number of images to generate
        )
    except Exception as error:
        print(str(error))
        raise gr.Error("An error occurred while generating speech. Please check your API key and come back try again.")

    return response.data[0].url


with gr.Blocks() as demo:
    gr.Markdown("# <center> Prompt de Resistance Image Generator</center>")
    gr.Markdown("**Instructions**: Generate an image from the text prompt below, then click the download arrow from the top right of the image to save it.")

    text = gr.Textbox(label="What do you want to create?",
                      placeholder="Enter your text and then click on the \"Image Generate\" button, "
                                  "or simply press the Enter key.")
    btn = gr.Button("Generate Image")
    output_image = gr.Image(label="Image Output")

    text.submit(fn=generate_image, inputs=[text], outputs=output_image, api_name="generate_image")
    btn.click(fn=generate_image, inputs=[text], outputs=output_image, api_name=False)

demo.launch(share=True)