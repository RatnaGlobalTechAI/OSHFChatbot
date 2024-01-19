from flask import Flask, render_template, request
from main import botMessage
from chatterbot import ChatBot
from chatterbot.trainers import ListTrainer


app = Flask(__name__)


# bot = ChatBot('Buddy')

# bot = ChatBot(
#     'Buddy',
#     storage_adapter='chatterbot.storage.SQLStorageAdapter',
#     database_uri='sqlite:///database.sqlite3'
# )

bot = ChatBot(
    'Buddy',  
    logic_adapters=[
        'chatterbot.logic.BestMatch',
        'chatterbot.logic.TimeLogicAdapter'],
)


trainer = ListTrainer(bot)

trainer.train([
'Hi',
'Hello',
"Hello %2, How are you today ?",
"I'm doing very well", "i am great !",
"Nice to hear that","Alright, great !",
"No rain in the past 4 days here in %2","In %2 there is a 50'%' chance of rain",
"I wanted to check my account balance.",
"check balance",
'I need your assistance regarding my order',
"apply for loan",
"its 3541",
'Please, Provide me with your order id',
'I have a complaint.',
'Please elaborate, your concern',
"my card number is 9876-7531-9514-8546",
'How long it will take to receive an order ?',
'Okay Thanks',
'No Problem! Have a Good Day!'
])


@app.route("/")
def index():
    return render_template("index.html")

@app.route("/get")
def get_bot_response():
    userText = request.args.get('msg')
    res = bot.get_response(userText)
    if res is not None:
        return str(res)
    else:
        return str(botMessage(userText))
    
    
if __name__ == "__main__":
    app.run()