
import os
import sys
import nltk

# Set the NLTK data path to be relative to the executable
nltk_data_dir = os.path.join(sys._MEIPASS, 'nltk_data')
os.makedirs(nltk_data_dir, exist_ok=True)
nltk.data.path.insert(0, nltk_data_dir)
