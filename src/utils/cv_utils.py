import cv2
import numpy as np
from PIL import Image, ImageDraw
from typing import List, Dict, Any, Tuple
import logging
from pathlib import Path
import warnings
warnings.filterwarnings("ignore", category=ResourceWarning, message="unclosed transport")

logger = logging.getLogger(__name__)

class ComputerVisionUtils:
    def __init__(self):
        self.visual_threshold = 0.95

    def compare_screenshots(self, image1_path: str, image2_path: str) -> Dict[str, Any]:
        """Compare two screenshots for visual regression testing"""
        try:
            img1 = cv2.imread(image1_path)
            img2 = cv2.imread(image2_path)
            
            if img1 is None or img2 is None:
                return {"error": "Could not load images"}
            
            # Resize images to same size if different
            if img1.shape != img2.shape:
                img2 = cv2.resize(img2, (img1.shape[1], img1.shape[0]))
            
            # Calculate similarity
            similarity = self._calculate_similarity(img1, img2)
            
            # Find differences
            diff_mask = self._create_diff_mask(img1, img2)
            
            # Generate diff image
            diff_image_path = self._create_diff_image(img1, img2, diff_mask, image1_path)
            
            return {
                "similarity": similarity,
                "passed": similarity >= self.visual_threshold,
                "diff_image": diff_image_path,
                "differences_found": np.sum(diff_mask) > 0
            }
            
        except Exception as e:
            logger.error(f"Error comparing screenshots: {e}")
            return {"error": str(e)}

    def detect_ui_elements(self, image_path: str) -> List[Dict[str, Any]]:
        """Detect UI elements in screenshot using computer vision"""
        try:
            img = cv2.imread(image_path)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            elements = []
            
            # Detect buttons (rectangles with text)
            buttons = self._detect_buttons(gray, img)
            elements.extend(buttons)
            
            # Detect text fields
            text_fields = self._detect_text_fields(gray, img)
            elements.extend(text_fields)
            
            # Detect images
            images = self._detect_images(gray, img)
            elements.extend(images)
            
            return elements
            
        except Exception as e:
            logger.error(f"Error detecting UI elements: {e}")
            return []

    def extract_text_regions(self, image_path: str) -> List[Dict[str, Any]]:
        """Extract text regions from screenshot"""
        try:
            img = cv2.imread(image_path)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Use MSER for text detection
            mser = cv2.MSER_create()
            regions, _ = mser.detectRegions(gray)
            
            text_regions = []
            for region in regions:
                x, y, w, h = cv2.boundingRect(region.reshape(-1, 1, 2))
                if w > 10 and h > 10:  # Filter small regions
                    text_regions.append({
                        "type": "text",
                        "bounds": {"x": x, "y": y, "width": w, "height": h},
                        "confidence": 0.8
                    })
            
            return text_regions
            
        except Exception as e:
            logger.error(f"Error extracting text regions: {e}")
            return []

    def _calculate_similarity(self, img1: np.ndarray, img2: np.ndarray) -> float:
        """Calculate structural similarity between images"""
        try:
            from skimage.metrics import structural_similarity as ssim
            
            # Convert to grayscale
            gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
            gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
            
            # Calculate SSIM
            similarity = ssim(gray1, gray2)
            return float(similarity)
            
        except ImportError:
            # Fallback to simple pixel comparison
            diff = cv2.absdiff(img1, img2)
            non_zero_count = np.count_nonzero(diff)
            total_pixels = img1.shape[0] * img1.shape[1] * img1.shape[2]
            similarity = 1.0 - (non_zero_count / total_pixels)
            return similarity

    def _create_diff_mask(self, img1: np.ndarray, img2: np.ndarray) -> np.ndarray:
        """Create a mask highlighting differences between images"""
        diff = cv2.absdiff(img1, img2)
        gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gray_diff, 30, 255, cv2.THRESH_BINARY)
        return mask

    def _create_diff_image(self, img1: np.ndarray, img2: np.ndarray, 
                          mask: np.ndarray, original_path: str) -> str:
        """Create a visual diff image showing differences"""
        try:
            # Create output path
            original_path = Path(original_path)
            diff_path = original_path.parent / f"{original_path.stem}_diff.png"
            
            # Create diff visualization
            diff_img = img2.copy()
            diff_img[mask > 0] = [0, 0, 255]  # Highlight differences in red
            
            cv2.imwrite(str(diff_path), diff_img)
            return str(diff_path)
            
        except Exception as e:
            logger.error(f"Error creating diff image: {e}")
            return ""

    def _detect_buttons(self, gray: np.ndarray, img: np.ndarray) -> List[Dict[str, Any]]:
        """Detect button-like elements"""
        buttons = []
        
        # Find contours
        contours, _ = cv2.findContours(gray, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            
            # Filter by size and aspect ratio (typical button characteristics)
            if 20 < w < 300 and 20 < h < 80 and 0.2 < h/w < 2:
                buttons.append({
                    "type": "button",
                    "bounds": {"x": x, "y": y, "width": w, "height": h},
                    "confidence": 0.7
                })
        
        return buttons

    def _detect_text_fields(self, gray: np.ndarray, img: np.ndarray) -> List[Dict[str, Any]]:
        """Detect text input fields"""
        text_fields = []
        
        # Detect rectangles (potential input fields)
        edges = cv2.Canny(gray, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            
            # Filter by typical input field dimensions
            if 50 < w < 400 and 15 < h < 50 and w/h > 2:
                text_fields.append({
                    "type": "input",
                    "bounds": {"x": x, "y": y, "width": w, "height": h},
                    "confidence": 0.6
                })
        
        return text_fields

    def _detect_images(self, gray: np.ndarray, img: np.ndarray) -> List[Dict[str, Any]]:
        """Detect image elements"""
        images = []
        
        # Simple approach: find large rectangular regions
        contours, _ = cv2.findContours(gray, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            
            # Filter by size (larger regions likely to be images)
            if w > 100 and h > 100:
                images.append({
                    "type": "image",
                    "bounds": {"x": x, "y": y, "width": w, "height": h},
                    "confidence": 0.5
                })
        
        return images

    def annotate_screenshot(self, image_path: str, elements: List[Dict[str, Any]]) -> str:
        """Annotate screenshot with detected elements"""
        try:
            img = Image.open(image_path)
            draw = ImageDraw.Draw(img)
            
            colors = {
                "button": "red",
                "input": "blue",
                "image": "green",
                "text": "orange"
            }
            
            for element in elements:
                bounds = element["bounds"]
                color = colors.get(element["type"], "purple")
                
                # Draw bounding box
                draw.rectangle([
                    bounds["x"], bounds["y"],
                    bounds["x"] + bounds["width"],
                    bounds["y"] + bounds["height"]
                ], outline=color, width=2)
                
                # Add label
                draw.text((bounds["x"], bounds["y"] - 15), 
                         element["type"], fill=color)
            
            # Save annotated image
            output_path = Path(image_path).parent / f"{Path(image_path).stem}_annotated.png"
            img.save(output_path)
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Error annotating screenshot: {e}")
            return image_path