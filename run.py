import multiprocessing
import os

def run_server():
    os.system('python server.py')

def run_bot():
    os.system('python main.py')

if __name__ == "__main__":
    server_process = multiprocessing.Process(target=run_server)
    bot_process = multiprocessing.Process(target=run_bot)

    server_process.start()
    bot_process.start()

    server_process.join()
    bot_process.join()