
# !pip install datasets
# !pip install chainlit
# !pip install farm-haystack[colab,inference,elasticsearch]

import chainlit as cl
from datasets import load_dataset
from haystack.document_stores import InMemoryDocumentStore
from haystack.nodes import PromptNode, PromptTemplate, AnswerParser, BM25Retriever
from haystack.pipelines import Pipeline
from haystack.utils import print_answers
import os
from dotenv import load_dotenv

# ---------------------- > 1

dataset = load_dataset("bilgeyucel/seven-wonders", split="train")

document_store = InMemoryDocumentStore(use_bm25=True)
document_store.write_documents(dataset)

retriever = BM25Retriever(document_store=document_store, top_k=3)

# ---------------------- > 2

prompt_template = PromptTemplate(
    prompt="""
    Documents:{join(documents)}
    Question:{query}
    Answer:
    """,
    output_parser=AnswerParser(),
)

# ---------------------- > 3

HF_TOKEN="your HF Token"

prompt_node = PromptNode(
    model_name_or_path="mistralai/Mistral-7B-Instruct-v0.1", api_key=HF_TOKEN, default_prompt_template=prompt_template
)

# ---------------------- > 4

generative_pipeline = Pipeline()
generative_pipeline.add_node(component=retriever, name="retriever", inputs=["Query"])
generative_pipeline.add_node(component=prompt_node, name="prompt_node", inputs=["retriever"])

# @cl.on_message
# async def main(message: str):
#     response = await cl.make_async(generative_pipeline.run)(message)
#     sentences = response['answers'][0].answer.split('\n')

#     # Check if the last sentence doesn't end with '.', '?', or '!'
#     if sentences and not sentences[-1].strip().endswith(('.', '?', '!')):
#         # Remove the last sentence
#         sentences.pop()

#     result = '\n'.join(sentences[1:])
#     await cl.Message(author="Bot", content=result).send()

# ---------------------- > 5

import re

def remove_chat_metadata(chat_export_file):
    date_time = r"(\d+\/\d+\/\d+,\s\d+:\d+)"  # e.g. "9/16/22, 06:34"
    dash_whitespace = r"\s-\s"  # " - "
    username = r"([\w\s]+)"  # e.g. "Martin"
    metadata_end = r":\s"  # ": "
    pattern = date_time + dash_whitespace + username + metadata_end

    with open(chat_export_file, "r") as corpus_file:
        content = corpus_file.read()
    cleaned_corpus = re.sub(pattern, "", content)
    return tuple(cleaned_corpus.split("\n"))




from chatterbot import ChatBot
from chatterbot.trainers import ListTrainer
from cleaner import clean_corpus


CORPUS_FILE = ""  #dataset file after it is loaded from above code

chatbot = ChatBot("Chatpot")

trainer = ListTrainer(chatbot)
cleaned_corpus = clean_corpus(CORPUS_FILE)
trainer.train(cleaned_corpus)

exit_conditions = (":q", "quit", "exit")
    
# ---------------------- > 7

def botMessage(message):
    sentences = (generative_pipeline.run)(message)['answers'][0].answer.split('\n')
    
    query = input("> ")
    if query in exit_conditions:
        # Check if the last sentence doesn't end with '.', '?', or '!'
        if sentences and not sentences[-1].strip().endswith(('.', '?', '!')):
            # Remove the last sentence
            sentences.pop()
    else:
        print(f"🪴 {chatbot.get_response(query)}")

    result = '\n'.join(sentences[1:])







