class Media:
    def __init__(self, media_type, file_path):
        self.media_type = media_type
        self.file_path = file_path


class Text(Media):
    def __init__(self, file_path):
        super().__init__('text', file_path)
        self.content = self._load_content()

    def _load_content(self):
        with open(self.file_path, 'r', encoding='utf-8') as f:
            return f.read()

    def get_content(self):
        return self.content

class TextGroup(Media):
    def __init__(self, file_path):
        super().__init__('text_group', file_path)
        self.texts = self._load_texts()

    def _load_texts(self):
        with open(self.file_path, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]

    def get_texts(self):
        return self.texts

class Image(Media):
    def __init__(self, file_path, resolution=None):
        super().__init__('image', file_path)
        self.resolution = resolution
        self.image_data = self._load_image()

    def _load_image(self):
        from PIL import Image as PILImage
        img = PILImage.open(self.file_path)
        if self.resolution:
            img = img.resize(self.resolution, PILImage.ANTIALIAS)
        return img

    def get_image(self):
        return self.image_data


class MotionPicture(Media):
    def __init__(self, file_path, resolution=None):
        super().__init__('motion_picture', file_path)
        self.resolution = resolution
        self.frames = self._load_frames()

    def _load_frames(self):
        from PIL import Image as PILImage
        img = PILImage.open(self.file_path)
        frames = []
        try:
            while True:
                if self.resolution:
                    img = img.resize(self.resolution, PILImage.ANTIALIAS)
                frames.append(img.copy())
                img.seek(img.tell() + 1)
        except EOFError:
            pass
        return frames

    def get_frames(self):
        return self.frames

