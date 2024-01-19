from chatterbot import ChatBot
from chatterbot.trainers import ListTrainer
from cleaner import clean_corpus
from datasets import load_dataset
from haystack.document_stores import InMemoryDocumentStore


dataset = load_dataset("bilgeyucel/seven-wonders", split="train")
document_store = InMemoryDocumentStore(use_bm25=True)
document_store.write_documents(dataset)

CORPUS_FILE = document_store

chatbot = ChatBot("Chatpot")

trainer = ListTrainer(chatbot)
cleaned_corpus = clean_corpus(CORPUS_FILE)
trainer.train(cleaned_corpus)

exit_conditions = (":q", "quit", "exit")
while True:
    query = input("> ")
    if query in exit_conditions:
        break
    else:
        print(f"🪴 {chatbot.get_response(query)}")
