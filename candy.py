#!/usr/bin/python

import logging
import random
import time
import threading
import pygame
import subprocess
from subprocess import PIPE

import RPi.GPIO as GPIO

class Ports():
    OPTO_1 = 17
    OPTO_2 = 21
    RELAY_1 = 18
    RELAY_2 = 23
    BUBBLE_MACHINE = 25
    KAHUNA_SWITCH = 22
    
    def __init__(self):
        # Initialize GPIO
        GPIO.setmode(GPIO.BCM)
        
        # Setup IO direction
        GPIO.setup(Ports.BUBBLE_MACHINE, GPIO.OUT)
        GPIO.setup(Ports.RELAY_1, GPIO.OUT)
        GPIO.setup(Ports.RELAY_2, GPIO.OUT)
        GPIO.setup(Ports.OPTO_1, GPIO.OUT)
        GPIO.setup(Ports.OPTO_2, GPIO.OUT)
  	GPIO.setup(Ports.KAHUNA_SWITCH, GPIO.IN)
    
    def __del__(self):
        GPIO.cleanup()

    def activate(self, port):
        GPIO.output(port, GPIO.HIGH)

    def deactivate(self, port):
        GPIO.output(port, GPIO.LOW)

    def ishigh(self, port):
        return GPIO.input(port)

class FakePorts():
    def __init__(self):
        logging.debug("Init ports")
    
    def __del__(self):
        logging.debug("Cleanup ports")
    
    def activate(self, port):
        logging.debug("Setting port %s HIGH" % port)

    def deactivate(self, port):
        logging.debug("Setting port %s LOW" % port)

# abstract class for actions
class Action():
    def __init__(self):
        pass

def perform(self):
        pass

class BubbleMachine(Action):
    def __init__(self, ports, stop_event, soundfx):
        self.ports = ports
        self.stop_event = stop_event
        self.soundfx = soundfx

    def perform(self):
        logging.info("BubbleMachine started")
       
        self.soundfx.fx_start(SoundFxGenerator.BUBBLES) 
        self.ports.activate(Ports.BUBBLE_MACHINE)
        time.sleep(10)
        self.ports.deactivate(Ports.BUBBLE_MACHINE)
        self.soundfx.fx_stop(SoundFxGenerator.BUBBLES) 

        logging.info("BubbleMachine stopped")

class SmokeMachine(Action):
    def __init__(self, ports, stop_event, soundfx):
        self.ports = ports
        self.stop_event = stop_event
        self.soundfx = soundfx
    
    def perform(self):
        logging.info("SmokeMachine started")
        
        self.soundfx.fx_start(SoundFxGenerator.SIREN) 
        self.ports.activate(Ports.RELAY_1)
        stop_event.wait(10)
        self.ports.deactivate(Ports.RELAY_1)
        self.soundfx.fx_stop(SoundFxGenerator.SIREN) 
        
        logging.info("SmokeMachine stopped")

class Bleeping(Action):
    def __init__(self, ports, stop_event, soundfx):
        self.ports = ports
        self.stop_event = stop_event
        self.soundfx = soundfx
    
    def perform(self):
        logging.info("Bleep started")
        
        self.soundfx.fx_start(SoundFxGenerator.BLEEP) 
        stop_event.wait(10)
        self.soundfx.fx_stop(SoundFxGenerator.BLEEP) 
        
        logging.info("Bleep stopped")

class Kahuna(Action):
    def __init__(self, ports, stop_event, soundfx):
        self.ports = ports;

    def perform(self):
        logging.info("Kahuna started")
        stop_event.wait(30)
        logging.info("Kahuna stopped")

class SoundFxGenerator():
    BUBBLES = 1
    SIREN = 2
    BLEEP = 3
    
    def __init__(self):
        # set audio output to the jack
        process = subprocess.Popen(["amixer", "cset", "numid=3", "1"] , stdin=PIPE, stdout=PIPE, stderr=PIPE)
        process.wait()
        pygame.mixer.init()
        self.effect_siren = pygame.mixer.Sound("soundeffects/police_s.wav")
        self.effect_bubbles = pygame.mixer.Sound("soundeffects/Bubbling-SoundBible.com-1684132696.wav")
        self.effect_bleep = pygame.mixer.Sound("soundeffects/bleep_01.wav")

    def __del__(self):
        pygame.mixer.quit()

    def fx_start(self, effect):
        effect = self.__get_effect_by_id(effect)
        effect.play(loops=-1)

    def fx_stop(self, effect):
        effect = self.__get_effect_by_id(effect)
        effect.stop()

    def __get_effect_by_id(self, id):
        if id == self.BUBBLES:
            return self.effect_bubbles
        elif id == self.SIREN:
            return self.effect_siren
        elif id == self.BLEEP:
            return self.effect_bleep

if __name__ == "__main__":
    logging.basicConfig(filename='/var/log/snoepjesmachine.log',
                        level=logging.DEBUG,
                        format='%(asctime)s %(message)s')
    
    gpioPorts = Ports()
    soundfx = SoundFxGenerator()
    stop_event = threading.Event()

    random.seed()
    
    randomActions = []
    randomActions.append(BubbleMachine(gpioPorts, stop_event, soundfx))
    randomActions.append(SmokeMachine(gpioPorts, stop_event, soundfx))
    randomActions.append(Bleeping(gpioPorts, stop_event, soundfx))

    kahuna = Kahuna(gpioPorts, stop_event, soundfx)
    
    lastAction = 0
    randomDeltaTime = 30 # Seconds
    kahunaFlag = False
    kahunaStarted = False
    actionThread = None

    while True:
        currentTime = time.time()

	if not gpioPorts.ishigh(Ports.KAHUNA_SWITCH) and kahunaFlag == False:
            logging.info("Kahuna event starting")
            kahunaFlag = True
            if not actionThread == None and not kahunaStarted:
                stop_event.set()
                logging.info("Event set, waiting for action to die")
                actionThread.join()
                logging.info("Action died, clearing event")
                stop_event.clear()
            if not kahunaStarted:
                actionThread = threading.Thread(target=kahuna.perform)
                actionThread.start()
                kahunaStarted = True
        elif gpioPorts.ishigh(Ports.KAHUNA_SWITCH) and kahunaFlag == True:
            if not actionThread == None and actionThread.isAlive():
                logging.info("Kahuna still running, not clearing the flag")
            else:
                logging.info("Kahuna event cleared")
                kahunaStarted = False
                kahunaFlag = False
        elif ((currentTime - lastAction) > randomDeltaTime) and not kahunaFlag:
            lastAction = time.time()
            logging.info("Time for a random action")
            action = random.randint(0, len(randomActions)-1)
            actionThread = threading.Thread(target=randomActions[action].perform)
            actionThread.start()
        
        logging.debug("regular poll, kahunaFlag = %s", kahunaFlag  )
        if not actionThread == None:
            actionThread.join(1)
            if not actionThread.isAlive():
                actionThread = None
        else:
            time.sleep(1)

