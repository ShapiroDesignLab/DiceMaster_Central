from ast import Pass
from mimetypes import init
import numpy as np

from .comm import Bus, SPIDevice
from .config import NUM_SCREEN, NUM_SPI_CTRL, NUM_DEV_PER_SPI_CTRL, IMG_RES_240SQ, \
    IMG_RES_480SQ, CHUNK_SIZE, MAX_TEXT_LEN, TXT_CMD, FONT_SIZE, TEXT_PADDING, SCREEN_WIDTH, BYTE_SIZE, USING_ORIENTED_SCREENS
from PIL import ImageFont

def HIBYTE(val):
    return (val >> 8) & 0xFF

def LOBYTE(val):
    return val & 0xFF


class Screen:
    """
    This is the screen class handing communication and context to and from each screen
    """

    def __init__(self, uid, bus, dev, bus_obj):
        self.id = uid
        self.spi_device = SPIDevice(uid, bus, dev)

        # Image Transfer Records
        self.last_img_id = 0

        # Register spi device to be pinged on bus
        bus_obj.register(self.spi_device)
        self.bus = bus_obj

    # Image Functions
    def draw_img(self, img_bytes, img_res=IMG_RES_480SQ, frame_time=0, orientation=0):
        """given an image in bytes, transfer the image over"""
        chunks = self.__make_img_chunks(
            img_bytes, CHUNK_SIZE, self.last_img_id, img_res, frame_time)
        # We Need Async Implementation (which it is now!)
        for chunk in chunks:
            pass
            # self.bus.queue(self.__build_msg(self.spi_device, IMG_CMD, chunk))

    @staticmethod
    def __make_img_chunks(img_bytearray, chunk_size, img_id, img_res=IMG_RES_480SQ, frame_time=0):
        """Make chunks of image from complete jpg file"""
        max_len = len(img_bytearray)
        chunk_id = 0
        chunks = []
        for start in range(0, max_len, chunk_size):
            # Get the chunk
            end = min(start+chunk_size, max_len)
            img_chunk = img_bytearray[start:end]

            # Build ID
            bit7 = 64*img_res + chunk_id + 128*(end == max_len)
            chunk = [img_id, bit7]

            # Append 0, after parity check
            chunk_len = end - start
            if chunk_len < chunk_size:
                zeros = [0] * (chunk_size + start - end)
                img_chunk.append(zeros)
            chunk.extend(img_chunk)

            # Add to all chunks
            chunks.append(chunk)
            chunk_id += 1
        return chunks

    # Text Functions
    def draw_text(self, color, text_list, lang):
        """Draw Text on screen"""
        # Build metadata
        msg = [TXT_CMD, TXT_CMD, TXT_CMD, TXT_CMD]

        # Add delay time
        msg.append(0)

        # Add color for block
        color = [(color//65536)%255, (color//256)%255, color%255]
        msg.extend([color[0], color[1], color[2]])

        # Add cursor position
        cursor_pos = Screen.__compute_text_cursor_position(text_list)
        xy_pos = [[HIBYTE(p[0]), LOBYTE(p[0]), HIBYTE(p[1]), LOBYTE(p[1])] for p in cursor_pos]

        # Set font
        font = self.__map_font(lang)

        # Build text line by line
        for i, (text, _) in enumerate(text_list):
            # Add cursor position
            msg.extend(xy_pos[i])
            msg.append(font)
            tb = bytearray(text+'\0', encoding='utf-8')
            if len(tb) < MAX_TEXT_LEN-len(msg)-1:
                msg.append(len(tb))
                msg.extend(list(tb))
            else:
                print(f"WARNING: single line of text longer than maximum of {MAX_TEXT_LEN} bytes!")
        self.bus.queue((self.spi_device, TXT_CMD, msg))

    @staticmethod
    def __map_font(lang: str):
        if lang.startswith('ar'): return 2  # Arabic
        if lang.startswith('zh'): return 3  # Chinese
        if lang.startswith('ru'): return 4  # Russian
        if lang.startswith('hi'): return 5  # Hindi
        return 1                            # Default to alphabetical (English, French, Spanish, etc)
        
    @staticmethod
    def __compute_text_cursor_position(text_list):
        """Computes list of tuples x,y as cursor locations for text"""
        cursor_pos = []
        
        # Load your specific fixed-width font and size
        font = ImageFont.truetype('unifont-12.1.02.ttf', FONT_SIZE)
        bbox = [font.getbbox(text[0]) for text in text_list]
        widths = [w[2] - w[0] for w in bbox]
        heights = [h[3] - h[1] for h in bbox]
        
        # Get size of the text
        width = max(widths)
        x_cursor = max(0, (SCREEN_WIDTH - width) // 2)

        height = max(heights)
        gap = height + TEXT_PADDING * (len(text_list) > 1)
        y_start = (SCREEN_WIDTH-gap*len(text_list)+TEXT_PADDING) // 2
        for i, (text, _) in enumerate(text_list):
            cursor_pos.append((x_cursor, y_start + gap*i))
        return cursor_pos

    # Option Menu Related Functions
    def draw_option(self, menu_items):
        """Draw Menu on screen"""
        pass

    # @staticmethod
    # def __parity(header, content):
    #     """Computes parity of bytes, """
    #     return (np.array(header).sum() + np.array(content).sum()) % BYTE_SIZE

    def send_array(self, barray):
        self.bus.queue((self.spi_device, TXT_CMD, barray))

    def draw(self):
        pass

class OrientedScreen(Screen):
    def __init__(self, uid, bus, dev, bus_obj, facing_orientation, top_orientation):
        super(OrientedScreen, self).__init__(uid, bus, dev, bus_obj)
        assert(isinstance(facing_orientation, np.ndarray))
        assert(isinstance(top_orientation, np.ndarray))
        self.init_facing_orientation = facing_orientation
        self.init_top_orientation = top_orientation

        self.screen_edge_orientations = [top_orientation
                            , np.cross(facing_orientation, top_orientation)
                            , -top_orientation
                            , - np.cross(facing_orientation, top_orientation)
                            ]
    
    def determine_gravitated_orientation(self):
        pass


class ScreenCollection:
    """A class representing an assembly of screens to interact with. 
        This class deals with geomeric relationships between screens. 
    """
    FACING_ORIENTATIONS = [
        np.array([0,0,1]),
        np.array([1,0,0]),
        np.array([0,1,0]),
        np.array([-1,0,0]),
        np.array([0,-1,0]),
        np.array([0,-1,0]),
    ]
    TOP_ORIENTATIONS = [
        np.array([1,0,0]),
        np.array([0,1,0]),
        np.array([-1,0,0]),
        np.array([0,-1,0]),
        np.array([1,0,0]),
        np.array([-1,0,0]),
    ]

    def __init__(self):
        # Build Bus
        self.bus = Bus()
        self.bus.run()

        # Build Screens 
        screen_cfg = self.__build_screen_config()
        self.screens = []
        for i, cfg in enumerate(screen_cfg):
            if USING_ORIENTED_SCREENS:
                self.screens.append(OrientedScreen(i+1, cfg["bus"], cfg["dev"], \
                                self.bus, self.FACING_ORIENTATIONS[i], self.TOP_ORIENTATIONS[i]))
            else:
                self.screens.append(Screen(i+1, cfg["bus"], cfg["dev"], \
                                self.bus))

        # Set Flags
        self.compute_orientation = USING_ORIENTED_SCREENS

    def sort_screen_faces(self):
        if not self.compute_orientation: 
            return None
        pass

    def __getitem__(self, id):
        return self.screens[id]

    def __build_screen_config(self):
        screen_cfg = []
        for bus in range(NUM_SPI_CTRL):
            for dev in range(NUM_DEV_PER_SPI_CTRL):
                if bus * 2 + dev == NUM_SCREEN:
                    return screen_cfg
                screen_cfg.append({"bus": bus,"dev": dev})
        return screen_cfg
     
if __name__ == "__main__":
    print("Error, calling module comm directly!")