from transformers import pipeline
from PIL import Image
import matplotlib.pyplot as plt

# load pipe
pipe = pipeline(task="depth-estimation", model="depth-anything/Depth-Anything-V2-Large-hf")

# load image from local path
image_path = 'lava-2114667_1280.jpg'
image = Image.open(image_path)

# inference
depth = pipe(image)["depth"]

# display the depth map
plt.imshow(depth, cmap='viridis')
plt.colorbar()
plt.title('Depth Estimation')
plt.show()
