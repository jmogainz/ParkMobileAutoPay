"""
Helper functions used to solve grid captcha
"""

import requests
import random
import base64
import time
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException


def configure_new_captcha_info_grid(self):
    # instruction
    # tests if captcha is on screen
    try:
        instruction = WebDriverWait(self.driver, 1).until(EC.presence_of_element_located((By.TAG_NAME, "strong"))).text
    except TimeoutException:
        return False

    # table
    self.recaptcha_table = self.driver.find_element(By.TAG_NAME, "table")
    self.grid_rows = len(self.recaptcha_table.find_elements(By.TAG_NAME, "tr"))
    self.grid_cols = len(self.recaptcha_table.find_element(By.TAG_NAME, "tr").find_elements(By.TAG_NAME, "td"))

    # get img source
    recaptcha_image = self.recaptcha_table.find_element(By.TAG_NAME, "img")
    img_src = recaptcha_image.get_attribute('src')
    response = requests.get(img_src)

    # convert to http request format
    self.img_string = base64.b64encode(response.content).decode('utf-8')
    self.instruction_string = f"Select all squares with {instruction}"

    return True

def request_2captcha_solution_grid(self):
    self.in_req_data = {'key': self.api_key_2captcha,
                    'method': 'base64',
                    'recaptcha': 1,
                    'lang': 'en',
                    'textinstructions': self.instruction_string,
                    'body': self.img_string,
                    'recaptcharows': self.grid_rows,
                    'recaptchacols': self.grid_cols,
                    'json': 1}

    # returns the id of request
    response = requests.post(self.captchaInputUrL, data=self.in_req_data)
    request_id = response.json()['request']

    self.res_req_dat = {'key': self.api_key_2captcha,
                    'action': 'get',
                    'id': request_id,
                    'json': 1}
    
def click_captcha_grid_buttons(self, buttons):
    captcha_grid_buttons = self.recaptcha_table.find_elements(By.TAG_NAME, "td")
    for button in buttons:
        captcha_grid_buttons[int(button)-1].click()

def skip_captcha_grid(self):
    verify_button = self.driver.find_element(By.ID, "recaptcha-verify-button")
    if verify_button.text == "Verify":
        random_buttons = random.sample(range(1, self.grid_rows*self.grid_cols+1), 4)
        click_captcha_grid_buttons(self, random_buttons)
    verify_button.click() # move to next captcha

    # check for confirm page in case randomly selected correct buttons
    try:
        WebDriverWait(self.driver, 5).until(lambda d: d.current_url == "https://app.parkmobile.io/zone/confirmation")
        return
    except TimeoutException:
        pass

    configure_new_captcha_info_grid(self)
    request_2captcha_solution_grid(self)

def gridSolve(self):
    try:
        recaptcha_iframe = WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.XPATH, ".//iframe[@title='recaptcha challenge expires in two minutes']")))
        self.driver.switch_to.frame(recaptcha_iframe)
        
        # Grid recaptcha
        if not configure_new_captcha_info_grid(self):
            print("[INFO] No recaptcha prompted. Processing payment...")
            return
        print(f"[INFO] Recaptcha prompted. Solving now...")

        # requests solution and builds the result request
        request_2captcha_solution_grid(self)

        # check for answer from 2captcha every 5 seconds
        # handle error codes
        start_time = time.time()
        while True:
            time.sleep(5)

            solution_found = False
            response = requests.get(self.captchaResultUrl, params=self.res_req_dat)
            if response.json()['status'] == 1:
                if response.json()['request'] == 'ERROR_BAD_DUPLICATES':
                    print("[WARNING] Workers could not agree. Resending captcha...")
                    response = requests.post(self.captchaInputUrL, data=self.in_req_data)
                    request_id = response.json()['request']
                    self.res_req_dat['id'] = request_id
                else:
                    print('[INFO] Solution is ready!', end=' ')
                    solution_found = True
            elif response.json()['request'] == 'CAPCHA_NOT_READY':
                print("[INFO] Solution not ready. Waiting 5 seconds...")
            elif response.json()['request'] == 'ERROR_CAPTCHA_UNSOLVABLE':
                print("[WARNING] No solution could be found. Skipping and sending new captcha...")
                skip_captcha_grid(self)

            # test if solution is correct
            if time.time() - start_time >= 120:
                break
            if solution_found:
                solution = response.json()['request'].split(':')[1].split('/')
                print(f"Squares: {solution}") 
                click_captcha_grid_buttons(self, solution)
                verify_button = self.driver.find_element(By.ID, "recaptcha-verify-button")
                verify_button.click()

                # check for confirm page
                try:
                    WebDriverWait(self.driver, 5).until(lambda d: d.current_url == "https://app.parkmobile.io/zone/confirmation")
                    break
                except TimeoutException:
                    print("[WARNING] Incorrect solution. Skipping and sending new captcha...")
                    skip_captcha_grid(self)
    except Exception as e:
        print(f"[ERROR] {e}")
        return

def hiddenV2Solve(self):
    try:
        # find anchor key
        recaptcha_div = WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, 'grecaptcha-logo')))
        iframe = recaptcha_div.find_element(By.TAG_NAME, "iframe")
        iframe_src = iframe.get_attribute('src')
        # extract the k value from the iframe src
        anchor_key = iframe_src.split('k=')[1].split('&')[0]

        in_req_data = {'key': self.api_key_2captcha,
                        'method': 'userrecaptcha',
                        'googlekey': anchor_key,
                        'pageurl': self.recaptchaInvisibleLocationUrl,
                        'invisible': 1,
                        'json': 1}

        # returns the id of request
        response = requests.post(self.captchaInputUrL, data=in_req_data)
        request_id = response.json()['request']

        res_req_dat = {'key': self.api_key_2captcha,
                    'action': 'get',
                    'id': request_id,
                    'json': 1}
        
        start_time = time.time()
        while True:
            time.sleep(5)

            solution_found = False
            response = requests.get(self.captchaResultUrl, params=res_req_dat)
            if response.json()['status'] == 1:
                if response.json()['request'] == 'ERROR_BAD_DUPLICATES':
                    print("[WARNING] Workers could not agree. Resending captcha...")
                    response = requests.post(self.captchaInputUrL, data=self.in_req_data)
                    request_id = response.json()['request']
                    self.res_req_dat['id'] = request_id
                else:
                    print('[INFO] Solution is ready!', end=' ')
                    solution_found = True
            elif response.json()['request'] == 'CAPCHA_NOT_READY':
                print("[INFO] Solution not ready. Waiting 5 seconds...")
            elif response.json()['request'] == 'ERROR_CAPTCHA_UNSOLVABLE':
                print("[WARNING] No solution could be found. Skipping and sending new captcha...")
                return False

            if time.time() - start_time >= 240:
                return False
            if solution_found:
                solution = response.json()['request']
                print(f"Solution: {solution}")
                self.driver.execute_script(f"document.getElementById('g-recaptcha-response').innerHTML=\"{solution}\";")
                time.sleep(2)
                self.driver.find_element(By.CLASS_NAME, "csvxiL").submit() # confirm payment

                # check for confirm page
                try:
                    WebDriverWait(self.driver, 5).until(lambda d: d.current_url == "https://app.parkmobile.io/zone/confirmation")
                    break
                except TimeoutException:
                    print("[WARNING] Incorrect solution. Skipping and sending new captcha...")
                    response = requests.post(self.captchaInputUrL, data=self.in_req_data)
                    request_id = response.json()['request']
                    self.res_req_dat['id'] = request_id
    except:
        return False

    return True

def solveRecaptcha(self):

    if not self.testing:
        print("[INFO] Performing preemptive captcha solving maneuvers...")
        if hiddenV2Solve(self):
            return

        print("[INFO] Preemptive measures failed...may use grid solve if necessary...")

    self.driver.find_element(By.CLASS_NAME, "csvxiL").submit() # confirm payment even if preemptive solve fails
    gridSolve(self)

    