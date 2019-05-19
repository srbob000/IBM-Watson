from watson_developer_cloud import TextToSpeechV1
from watson_developer_cloud import LanguageTranslatorV2 as LanguageTranslator
from ws4py.client.threadedclient import WebSocketClient
import base64, json, ssl, subprocess, threading, time, requests, webbrowser


# These are from the Audio Example
import pyaudio
import time
import wave

# open stream
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
RATE = 48000
CHUNK = 24000  # was 2048, made this 2000 to divide evenly into 16000, smoothed out the playback

# https://2001archive.org/
wf_greeting = wave.open('greetings.wav', 'rb')
wf_goodbye =  wave.open('goodbye.wav', 'rb')
wf_ignore = wave.open('sure.wav','rb')

'''
Port Audio seems to have some known issues.
'''

language_translator = LanguageTranslator(
   username= '',
   password='')

def textToSpeech(self):
    text_to_speech = TextToSpeechV1(
        username= "c64f8040-2d49-4274-bd33-f9e746876392",
        password="xOpWo4tcLLYv",)

    print(json.dumps(text_to_speech.voices(), indent=2))
    p = pyaudio.PyAudio()

    stream = p.open(format=p.get_format_from_width(2),
                channels=1,
                rate=22050,
                output=True)

    stream.write(
        text_to_speech.synthesize(self, accept='audio/wav',
                                  voice="en-GB_KateVoice"))

    p.terminate()


def play_uncompressed_wave(wave_object):
    # define callback (2)
    def callback(in_data, frame_count, time_info, status):
        data = wave_object.readframes(frame_count)
        return data, pyaudio.paContinue

    # instantiate PyAudio (1)
    p_out = pyaudio.PyAudio()
    stream_out = p_out.open(format=p_out.get_format_from_width(wave_object.getsampwidth()),
                            channels=wave_object.getnchannels(),
                            rate=wave_object.getframerate(),
                            output=True,
                            stream_callback=callback)

    # start the stream (4)
    stream_out.start_stream()

    # wait for stream to finish (5)
    while stream_out.is_active():
        time.sleep(0.1)

    # stop stream (6)
    stream_out.stop_stream()
    stream_out.close()
    wave_object.close()
    p_out.terminate()
    pass


class SpeechToTextClient(WebSocketClient):
    def __init__(self):
        ws_url = "wss://stream.watsonplatform.net/speech-to-text/api/v1/recognize"

        username = "d12b13c6-dc6a-40f7-a1c1-343a70ae59f4"
        password = "JcAPXsLMcB78"

        authstring = "{0}:{1}".format(username, password)
        base64string = base64.b64encode(authstring.encode('utf-8')).decode('utf-8')

        self.Command_State = None
        self.listening = False
        self.empty_count = 0
        self.Gathered_String = ''
        self.stream_audio_thread = threading.Thread(target=self.stream_audio)
        try:
            WebSocketClient.__init__(self, ws_url,
                                     headers=[("Authorization", "Basic %s" % base64string)])
            self.connect()
        except:
            print("Failed to open WebSocket.")

    def opened(self):
        #self.send('{"action": "start", "content-type": "audio/l16;rate=44100;channels=1" }')
        data = {"action": "start",
                "content-type": "audio/l16;rate=44100;channels=1",
                'max_alternatives': 3,
                "keywords": ["Watson","quit"],
                "keywordsThreshold":0.5,
                'timestamps': True,
                'word_confidence': True}

        print("sendMessage(init)")
        # send the initialization parameters
        print(json.dumps(data).encode('utf8'))
        self.send(json.dumps(data).encode('utf8'))
        self.stream_audio_thread.start()

    def received_message(self, message):

        message = json.loads(str(message))

        if "state" in message:
            if message["state"] == "listening" and self.Command_State is None:
                play_uncompressed_wave(wf_greeting)
                self.listening = True
        if "results" in message:
            print(self.Command_State)
            if message["results"]:
                x = message['results']
                print(x)

                if x[0]['alternatives'][0]['transcript'] == 'Watson ' and self.Command_State is None:
                    print("found a command")
                    self.Command_State = 'Started'
                if x[0]['alternatives'][0]['transcript'] == 'ignore ' and self.Command_State is 'Started':
                    play_uncompressed_wave(wf_ignore)
                    self.Command_State = None
                    self.listening = True
                if x[0]['alternatives'][0]['transcript'] == 'go ' and self.Command_State is 'Started':
                    self.Command_State = 'Gather'
                    self.Gathered_String = ''
                    self.listening = True
                    self.empty_count = 0
                if x[0]['alternatives'][0]['transcript'] == 'browser ':
                    self.listening = True
                    webbrowser.open_new("https://www.google.com")

                if x[0]['alternatives'][0]['transcript'] == 'quit ':
                    self.listening = False
                    play_uncompressed_wave(wf_goodbye)
                    self.Command_State = 'Exit'
                    self.stream_audio_thread.join()

                if self.Command_State == 'Gather':
                    self.Gathered_String = self.Gathered_String + x[0]['alternatives'][0]['transcript']
                    self.empty_count = 0

            else:
                if self.Command_State == 'Gather':
                    self.empty_count = self.empty_count + 1
                    if self.empty_count >= 3:
                        self.Command_State = None
                        self.listening = True
                        # HERE IS WHERE YOU WILL SEND THE Gathered_String
                        print(self.Gathered_String)

                        translation = language_translator.translate(
                            text=self.Gathered_String,
                            source='en', target='fr')

                        print(json.dumps(translation, indent=2, ensure_ascii=False))

                        #textToSpeech(translation)

    def stream_audio(self):
        print("Waiting for Watson")
        while not self.listening:
            time.sleep(0.1)
        print("Hello Watson")
        p_in = pyaudio.PyAudio()
        iChunk = 4410
        iSec = 1
        stream_in = p_in.open(format=pyaudio.paInt16, channels=1, rate=44100, input=True, frames_per_buffer=iChunk)

        while self.listening:
            for i in range(0, int(44100 / iChunk * iSec)):
                data = stream_in.read(CHUNK, exception_on_overflow=False)
                if data:
                    try:
                        self.send(bytearray(data), binary=True)
                    except ssl.SSLError:
                        pass
                    except ConnectionAbortedError:
                        pass
            if self.listening:
                try:
                    self.send('{"action": "stop"}')
                except ssl.SSLError:
                    pass
                except ConnectionAbortedError:
                    pass
            time.sleep(0.5)

        stream_in.stop_stream()
        stream_in.close()
        p_in.terminate()
        self.close()

    def close(self,code=1000, reason=''):

        self.listening = False
        WebSocketClient.close(self)


if __name__ == "__main__":

    stt_client = SpeechToTextClient()

    while not stt_client.terminated:
        pass
