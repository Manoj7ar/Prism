from utils.screen_utils import get_screen_resolution, get_dpi_scale
import pyautogui
from PIL import Image

print('PyAutoGUI size:', pyautogui.size())
print('Screen resolution:', get_screen_resolution())
print('DPI scale:', get_dpi_scale())

# Take a screenshot and check its actual dimensions
ss = pyautogui.screenshot()
print('Screenshot dimensions:', ss.size)
