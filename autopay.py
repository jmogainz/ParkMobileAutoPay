"""
Scrape Park Mobile Web App and pay for parking based on configuration
"""

from xtra_info import ua_list
from tkinter import Tk
from tkinter import filedialog as fd
import os
import sys
from yaml import safe_load as yaml_load
import json
import datetime
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import TimeoutException
import random
from selenium_stealth import stealth
from http_request_randomizer.requests.proxy.requestProxy import RequestProxy
from selenium.webdriver.common.proxy import Proxy, ProxyType
from captchaSolving import solveRecaptcha
import string

# simple class to convert yaml and json files to pythonic objects
class RecursiveNamespace:
  @staticmethod
  def map_entry(entry):
    if isinstance(entry, dict):
        return RecursiveNamespace(**entry)
    return entry
  def __init__(self, **kwargs):
    for key, val in kwargs.items():
        if type(val) == dict:
            setattr(self, key, RecursiveNamespace(**val))
        elif type(val) == list:
            setattr(self, key, list(map(self.map_entry, val)))
        else:
            setattr(self, key, val)


class AutoPayer:
    def __init__(self):
        self.email = ''
        self.phone = 0000000000
        self.api_key_2captcha = '44729098de65174e3502fa34b9856733'
        self.parkMobileUrl = 'https://parkmobile.io/zone/start'
        self.driver = None
        self.hour_options = [0, 1, 2, 3, 4] # configured based on Park Mobile location (Starkville)
        self.minute_options = [0, 15, 30, 45] # configured based on Park Mobile location (Starkville)
        self.retry_limit = 60 * 1 # 1 minute
        self.total_price = ''
        self.testing = False

        # captcha info
        self.captchaInputUrL = 'http://2captcha.com/in.php'
        self.captchaResultUrl = 'http://2captcha.com/res.php'
        self.recaptchaInvisibleLocationUrl = 'https://app.parkmobile.io/zone/review'
        self.grid_rows = 0
        self.grid_cols = 0
        self.recaptcha_table = None
        self.in_req_data = {}
        self.res_req_data = {}

        # payment info
        self.card_number = 0000000000000000
        self.card_cvv = 000
        self.card_exp = 'MM/YY'
        self.card_zip = 00000
        self.card_country = 'US'

        # parking info
        self.park_zone = 14706
        self.park_zone_location = 'Starkville, MS'
        self.park_duration_hours = 0
        self.park_duration_minutes = 0
        self.license_plate = ''
        self.plate_country = 'US'
        self.plate_state = 'AL'

        # launch time
        self.payment_time_year = 0
        self.payment_time_month = 0
        self.payment_time_day = 0
        self.payment_time_hour = 0
        self.payment_time_minute = 0
    
    def loadConfig(self, config):
        self.testing = config.testing

        if config.payment_time:
            self.payment_time_year = config.payment_time.year
            self.payment_time_month = config.payment_time.month
            self.payment_time_day = config.payment_time.day
            self.payment_time_hour = config.payment_time.hour
            self.payment_time_minute = config.payment_time.minute

        if config.payment_info:
            if len(str(config.payment_info.number)) != 16:
                sys.exit("[ERROR] Card number must be 16 digits. Exiting...")
            self.card_number = config.payment_info.number
            
            self.card_cvv = config.payment_info.cvv
            self.card_exp = f"{config.payment_info.exp.month}/{config.payment_info.exp.year}"
            self.card_zip = config.payment_info.zip
            self.card_country = config.payment_info.country
            self.email = config.payment_info.email
            if config.payment_info.phone:
                self.phone = config.payment_info.phone

        if config.parking_info:
            self.park_zone = config.parking_info.zone
            self.park_zone_location = f"{config.parking_info.zone_city}, {config.parking_info.zone_state}"

            # verify input duration is valid for current configured location
            if (config.parking_info.duration.hours in self.hour_options and
                config.parking_info.duration.minutes in self.minute_options):
                if (config.parking_info.duration.hours == self.hour_options[-1] and
                    config.parking_info.duration.minutes > self.minute_options[0]):
                    print(f"[ERROR] Invalid duration for current Park Mobile location: Cannot park for more than {self.hour_options[-1]} hours")
                    sys.exit(1)
                if (config.parking_info.duration.hours == 0 and
                    config.parking_info.duration.minutes == 0):
                    print("[ERROR] Invalid duration for current Park Mobile location: Cannot park for duration of 0")
                    sys.exit(1)
                self.park_duration_hours = config.parking_info.duration.hours * 60
                self.park_duration_minutes = config.parking_info.duration.minutes

            self.license_plate = config.parking_info.plate
            self.plate_country = config.parking_info.plate_country
            self.plate_state = config.parking_info.plate_state
            self.hour_options = config.parking_info.desired_location_hour_limits
            self.minute_options = config.parking_info.desired_location_minute_limits

    def configureWebDriver(self):
        service = ChromeService(executable_path=ChromeDriverManager().install())

        chrome_options = Options()
        # chrome_options.add_argument("--headless")
        # chrome_options.add_argument(f"--window-size={random.randint(800, 1080)},{random.randint(1080, 1920)}")
        # chrome_options.add_argument(f"user-agent={random.choice(ua_list)}")
        chrome_options.add_experimental_option("prefs", { "profile.default_content_setting_values.geolocation": 2})
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        # chrome_options.add_argument("--proxy-server=http://82.102.11.166:80")

        # request_proxy = RequestProxy()
        # PROXY = request_proxy.get_proxy_list()[0].get_address()

        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.driver.delete_all_cookies()
        stealth(self.driver,
            languages=["en-US", "en"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True,
            )

        self.driver.get(self.parkMobileUrl)

    def enterZone(self):
        zone_entry = WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.ID, "signageCode")))
        time.sleep(0.5)
        zone_entry.send_keys(self.park_zone)
        self.driver.find_element(By.CLASS_NAME, "cjODfJ").submit() # submit zone

        try:
            locations_div = WebDriverWait(self.driver, 3).until(EC.presence_of_element_located((By.CLASS_NAME, "kaFRKK"))) # wait for location prompt
            # check the text of each button to see if it matches the desired location
            for button in locations_div.find_elements(By.TAG_NAME, "button"):
                if button.text == self.park_zone_location:
                    button.click()
                    break
        except:
            pass
            
        WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "gUDBFT"))) # wait until location is determined
        self.driver.find_element(By.CLASS_NAME, "cjODfJ").click() # submit zone again

    def enterDuration(self):
        WebDriverWait(self.driver, 5).until(lambda d: d.current_url == "https://app.parkmobile.io/zone/duration")   
        try:
            WebDriverWait(self.driver, 1).until(EC.presence_of_element_located((By.ID, "rate-maximum-parking-time"))).click()
        except TimeoutException:
            pass
        
        if not self.testing:
            # try to set duration, except and return false if duration unavailable
            try:
                hour_select_box = WebDriverWait(self.driver, 1).until(EC.presence_of_element_located((By.ID, "hours")))
                if not (hour_select_box.is_enabled() and hour_select_box.is_displayed()):
                    raise Exception

                minute_select_box = self.driver.find_element(By.ID, "minutes")
                hour_select_obj = Select(hour_select_box)
                minute_select_obj = Select(minute_select_box)
                
                # if hour option is not available at particular time, park for maximum possible duration
                curr_hour_opts = [int(x.get_attribute("value")) for x in hour_select_box.find_elements(By.TAG_NAME, "option")]
                curr_minute_opts = [int(x.get_attribute("value")) for x in minute_select_box.find_elements(By.TAG_NAME, "option")]
                if self.park_duration_hours not in curr_hour_opts:
                    print(f"[WARNING] Hour option {self.park_duration_hours} not available at this time." 
                        "Parking for maximum duration of {curr_hour_opts[-1]} hours and {curr_minute_opts[-1]} minutes...")
                    self.park_duration_hours = curr_hour_opts[-1]
                    self.park_duration_minutes = curr_minute_opts[-1]
                
                hour_select_obj.select_by_value(str(self.park_duration_hours))
                minute_select_obj.select_by_value(str(self.park_duration_minutes))

            except NoSuchElementException and Exception:
                print("[WARNING] Could not select a duration. Parking is most likely free right now...Retrying in 5 seconds...")
                return False

        WebDriverWait(self.driver, 5).until(lambda d: d.find_element(By.CLASS_NAME, "cjODfJ")).submit() # submit duration

        return True

    def enterLicenseInfo(self):
        WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "bsCqQK"))).click() # continue as guest

        WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.ID, "lpn"))).send_keys(self.license_plate)
        country_select_obj = Select(self.driver.find_element(By.ID, "country"))
        country_select_obj.select_by_value(self.plate_country)
        state_select_obj = Select(self.driver.find_element(By.ID, "state"))
        state_select_obj.select_by_value(self.plate_state)
        self.driver.find_element(By.CLASS_NAME, "cjODfJ").submit() # submit license info

    def enterPaymentInfo(self):
        WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.ID, "cardNumber"))).send_keys(self.card_number)
        time.sleep(0.5)
        self.driver.find_element(By.ID, "expiration").send_keys(self.card_exp)
        time.sleep(0.5)
        self.driver.find_element(By.ID, "securityCode").send_keys(self.card_cvv)
        country_select_obj = Select(self.driver.find_element(By.ID, "country"))
        country_select_obj.select_by_value(self.card_country)
        time.sleep(0.5)
        self.driver.find_element(By.ID, "zipCode").send_keys(self.card_zip)
        time.sleep(0.5)
        self.driver.find_element(By.ID, "email").send_keys(self.email)
        time.sleep(0.5)
        self.driver.find_element(By.CLASS_NAME, "cjODfJ").submit() # submit payment info

    def confirmPayment(self):
        phone_entry = WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.ID, "mobileNumber")))
        if self.phone:
            phone_entry.send_keys(self.phone)

        time.sleep(0.5)

        # grab total cost
        cost_div = self.driver.find_element(By.CLASS_NAME, "loLOKo")
        self.total_price = cost_div.find_element(By.CLASS_NAME, "dtZRuz").text

        solveRecaptcha(self)

        try:
            WebDriverWait(self.driver, 10).until(lambda d: d.current_url == "https://app.parkmobile.io/zone/confirmation")
        except TimeoutException:
            print("[ERROR] Payment timed out at captcha. Solve attempt failed. Retrying in 5 seconds...")
            return False

        # safety wait
        time.sleep(2)

        return True

    def park(self):
        start = time.time()

        if not self.testing:
            while True:
                try:
                    while True:
                        self.configureWebDriver()
                        self.enterZone()
                        if self.enterDuration():
                            break
                        if (time.time() - start) > self.retry_limit:
                            print("[ERROR] Could not select a duration. Parking is most likely free right now. Exiting...")
                            sys.exit(1)
                        self.driver.quit()

                    self.enterLicenseInfo()
                    self.enterPaymentInfo()
                    if self.confirmPayment():
                        break
                    self.driver.quit()
                except Exception as e:
                    print(f"[ERROR] {e}")
                    print("[INFO] Recovering...")
                    try:
                        self.driver.quit()
                    except:
                        pass
        else:
            while True:
                self.license_plate = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(7))
                self.configureWebDriver()
                self.enterZone()
                self.enterDuration()
                self.enterLicenseInfo()
                self.enterPaymentInfo()
                self.confirmPayment()
                self.driver.quit()

    def launch(self):
        if not self.testing:
            current_time = datetime.datetime.now()
            launch_time = datetime.datetime(self.payment_time_year, 
                                            self.payment_time_month, 
                                            self.payment_time_day, 
                                            self.payment_time_hour, 
                                            self.payment_time_minute)
            total_seconds = (launch_time - current_time).total_seconds()
            
            print(f"[INFO] Waiting {total_seconds} seconds until {launch_time}")
            if total_seconds > 0:
                time.sleep(total_seconds) # wait until launch time
            else:
                sys.exit("[ERROR] Launch time has already passed. Fix config file and try again. Exiting...")

        print("[INFO] Parking now...")
        self.park()

        print(f"[INFO] Successfully paid for {self.park_duration_hours / 60} hours and {self.park_duration_minutes} minutes of parking --> Total cost: {self.total_price}")

        input("[INFO] Press enter to exit...")

def launchParkMobilePayer(config):
    auto_payer = AutoPayer()
    auto_payer.loadConfig(config)
    auto_payer.launch()

def main():
    def get_path(wildcard):
        root = Tk()
        root.withdraw()
        file_path = \
            fd.askopenfilename(parent=None, defaultextension='.json, .yml, .yaml',
                               initialdir=os.getcwd(),
                               title="Choose ML Test Python Input Configuration (Server)",
                               filetypes=[("JSON OR YAML Config", wildcard)])
        root.update()
        root.destroy()
        return file_path

    if len(sys.argv) > 1 and sys.argv[1] == '--custom':
        # call file explorer
        configFile = get_path('*.json *.yml *.yaml')
    else:
        # get the absolute path to the first .yaml file found in working directory
        configFile = [os.path.join(os.getcwd(), f) for f in os.listdir(os.getcwd()) if f.endswith('.yaml')][0]

    # check if config file path exists
    if os.path.exists(configFile):
        print('[INFO] Config file found: ' + configFile)
    else:
        print('[ERROR] Config file not found: ' + configFile)
        sys.exit(1)

    # verify file is of valid type
    if configFile.lower().endswith("yaml") or configFile.lower().endswith("yml"):
        config = yaml_load(open(configFile, 'r'))
        config = RecursiveNamespace(**config)
    elif configFile.lower().endswith("json"):
        config = json.load(open(configFile))
        config = RecursiveNamespace(**config)
    else:
        print('[ERROR] Invalid config file type')
        sys.exit(1)
    
    launchParkMobilePayer(config)


if __name__ == '__main__':
    main()

    


    
        
        