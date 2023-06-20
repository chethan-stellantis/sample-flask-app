from flask import Flask, render_template, request
#from selenium import webdriver
#from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
# from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
# from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver import Chrome
from selenium.webdriver.common.action_chains import ActionChains
# import time
import json#, time
from flask_socketio import SocketIO, emit, join_room, leave_room

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins='*')
webdrivers = {}
client_auths = {}
url = None

# chrome_options = Options()
# chrome_options.add_argument("--headless")
# driver = Chrome()#webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
# driver.get("https://connect.jeep.com/us/en/login")
# driver.implicitly_wait(5)


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/auth', methods=['POST'])
def verify():
    if request.method == 'POST':
        data = request.get_json()
        print(f"data {data}")
        client_auths[data['sid']] = data
        socketio.emit('credentials', data, room=data['sid'])
        return f"data received {data}"
    else:
        return "Method not allowed"


@socketio.on('connect')
def on_connect():
    try:
        client_sid = request.sid
        join_room(client_sid)
        print(f"client sid {client_sid}")
        chrome_options = Options()
        # chrome_options.add_argument("--headless")
        driver = Chrome(options=chrome_options)
        webdrivers[client_sid] = driver
        emit('connected', client_sid)
    except Exception as e:
        print(f"Client {client_sid}, error: {e}")
        emit('error', client_sid)

@socketio.on('disconnect')
def on_disconnect():
    try:
        print(f"client id {request.sid} disconnected")
        client_sid = request.sid
        driver = webdrivers.get(client_sid)
        if driver:
            # we may not be able to send event on closed socket at this point!
            # emit('disconnected')
            driver.quit()
            del webdrivers[client_sid]
        leave_room(client_sid)
    except Exception as e:
        print(f"Client {client_sid}, error: {e}")
        emit('error', client_sid)

@socketio.on('load')
def load(data):
    try:
        client_sid = request.sid
        driver = webdrivers.get(client_sid)
        driver.get(data['url'])
        driver.implicitly_wait(5)
        print(f"client sid {client_sid} driver sid {driver.session_id} url {data['url']}")
        emit('loaded', {'url': driver.current_url, 'code': data['code']})
    except Exception as e:
        print(f"Client {client_sid}, error: {e}")
        emit('error', client_sid)

@socketio.on('pageSource')
def pageSource():
    try:
        client_sid = request.sid
        driver = webdrivers.get(client_sid)
        emit('page_source', json.dumps(driver.page_source))
    except Exception as e:
        print(f"Client {client_sid}, error: {e}")
        emit('error', client_sid)

@socketio.on('sendEvent')
def sendEvent(data):
    try:
        print(f"send event")
        client_sid = request.sid
        driver = webdrivers.get(client_sid)
        elements = data['elements']
        element = None
        for e in elements:
            print(f"load {e['element']} {e['value']} {e['type']} {e['action']}")
            if 'id' in e['type']:
                element = driver.find_element(By.ID, e['element'])
            elif 'class' in e['type']:
                if e['index'] >= 0:
                    element = driver.find_elements(By.CLASS_NAME, e['element'])
                else:
                    element = driver.find_element(By.CLASS_NAME, e['element'])
            if 'submit' in e['action']:
                element.send_keys(e['value'])
                element.submit()
            elif 'enter' in e['action']:
                if e['index'] >= 0:
                    button_element = element[e['index']].find_element(By.CLASS_NAME, e['iElement'])
                    button_element.send_keys(Keys.ENTER)
                else:
                    element.send_keys(Keys.ENTER)
            elif 'click' in e['action']:
                if e['index'] >= 0:
                    # FIXME: what if it is not class but id
                    if len(e['iElement']):
                        button_element = element[e['index']].find_element(By.CLASS_NAME, e['iElement'])
                    else:
                        button_element = element[e['index']]
                    driver.execute_script("arguments[0].click();", button_element)
                else:
                    try:
                        driver.execute_script("arguments[0].click();", element)
                    except Exception as e:
                        print("-->"+str(e))
            else:
                element.send_keys(e['value'])
            wait = WebDriverWait(driver, 20)
        expected = data['expected']
        length = len(expected['text'])
        print(" length of the expected text in string "+ str(length))
        if 'class' in expected['type']:
            if (length):
                wait.until(EC.text_to_be_present_in_element((By.CLASS_NAME, expected['element']), expected['text']))
            else:
                wait.until(EC.presence_of_element_located((By.CLASS_NAME, expected['element'])))
        elif 'id' in expected['type']:
            if (length):
                wait.until(EC.text_to_be_present_in_element((By.ID, expected['element']), expected['text']))
            else:
                wait.until(EC.presence_of_element_located((By.ID, expected['element'])))
        emit('event_done', data['eventCode'])
    except Exception as e:
        print(f"Client {client_sid}, error: {e}")
        #emit('error', client_sid)

@socketio.on('getCredentials')
def on_getCredentials(data):
    try:
        client_sid = request.sid
        print(f"getting creadentials {data['pin']} {client_auths[client_sid]['pin']}")
        response = client_auths[client_sid]
        if(data['pin'] == client_auths[client_sid]['pin']):
            response['statuscode'] = 200
        else:
            response['statuscode'] = 403
        emit('credentials', response)
    except Exception as e:
        print(f"Client {client_sid}, error: {e}")
        emit('error', e)

@socketio.on('login')
def login(data):
    try:
        client_sid = None
        element = None
        for key in data:
            print("KEY "+key+" "+data[key])
            client_sid = request.sid
            driver = webdrivers.get(client_sid)
            element = driver.find_element(By.ID, str(key))
            element.send_keys(str(data[key]))
        element.submit()
        wait = WebDriverWait(driver, 20)
        # wait.until(EC.url_matches("https://connect.jeep.com/us/en/dashboard"))
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'card-body')))
        elements = driver.find_elements(By.CLASS_NAME, "card-footer")
        data = []
        for element in elements:
            subelement = element.find_element(By.TAG_NAME, 'a')
            href = subelement.get_attribute("href")
            title = subelement.get_attribute("title")
            print("href "+href+"\ntitle "+title)
            response = {
                'title': title,
                'link': href
            }
            data.append(response)
        emit('features', json.dumps(data))
    except Exception as e:
        print(f"Client {client_sid}, error: {e}")
        emit('error', client_sid)

if __name__ == '__main__':
    socketio.run(app)
