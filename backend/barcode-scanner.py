import cv2
from pyzbar.pyzbar import decode

class BarcodeScanner:
    def __init__(self, camera_index=0):
        self.camera_index = camera_index
        self.cap = cv2.VideoCapture(self.camera_index)
        
    def scan_from_image(self, image_path):
        """Scan barcodes from an image file."""
        
        image = cv2.imread(image_path)
        
        if image is None:
            print("Error: Could not read image.")
            return 
        
        barcodes = decode(image)  # returns list of decoded objects [web:22][web:25]
        
        if not barcodes:
            print("No barcodes found.")
            return
        
        for barcode in barcodes:
            x, y, w, h = barcode.rect
            cv2.rectangle(image, (x, y), (x + w, y + h), (0, 255, 0), 2)

            data = barcode.data.decode("utf-8")
            btype = barcode.type
            text = f"{btype}: {data}"

            cv2.putText(image, text, (x, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            print(text)

        cv2.imshow("Barcode Image", image)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
        
    def scan_from_camera(self):
        """Scan barcodes/QR codes from the webcam."""
        # cap = cv2.VideoCapture(self.camera_index)

        if not self.cap.isOpened():
            print("Error: Could not open camera.")
            return

        print("Press 'q' to quit.")

        while True:
            ret, frame = self.cap.read()
            if not ret:
                break

            barcodes = decode(frame)  # works on each frame [web:20][web:27]

            for barcode in barcodes:
                x, y, w, h = barcode.rect
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

                data = barcode.data.decode("utf-8")
                btype = barcode.type
                text = f"{btype}: {data}"

                cv2.putText(frame, text, (x, y - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

                print(text)

            cv2.imshow("Barcode Scanner (Camera)", frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        self.cap.release()
        cv2.destroyAllWindows()
        
        
if __name__ == "__main__":
    scanner = BarcodeScanner(camera_index=0)
    # For image:
    # scanner.scan_from_image("path/to/image.png")
    # For camera:
    scanner.scan_from_image("bar-code.jpeg")
    

        