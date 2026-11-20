import cv2
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
from ultralytics import YOLO
import os
import json
import time
from pathlib import Path

# Initial settings
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
BACKEND_ROOT = Path(__file__).resolve().parent
DEFAULT_MODEL_PATH = BACKEND_ROOT / "yolov8" / "olive-yolov8n-v2.pt"

# Helper functions
def load_image(image_path):
    return cv2.imread(image_path)

def load_yolo_model():
    model_path = Path(os.environ.get("OLIVE_MODEL_PATH", DEFAULT_MODEL_PATH))
    if not model_path.is_file():
        raise FileNotFoundError(
            "YOLOv8 weights were not found. Set OLIVE_MODEL_PATH to a local "
            f".pt file or place the weights at {DEFAULT_MODEL_PATH}."
        )
    return YOLO(str(model_path))

def run_yolo_inference(model, image_path, conf=0.6):
    return model.predict(source=image_path, conf=conf)

def enhance_image(image):
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    hsv[..., 1] = cv2.multiply(hsv[..., 1], 2)
    hsv[..., 2] = cv2.multiply(hsv[..., 2], 1.5)
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

def estimate_weight_from_bbox_ellipse(width, height, weight_per_pixel=0.003):
    """
    Estimate the olive weight (raw and clamped) based on the bounding box area.

    Args:
        width (int): Bounding box width in pixels.
        height (int): Bounding box height in pixels.
        weight_per_pixel (float): Weight-per-pixel scaling factor.

    Returns:
        tuple: (estimated_weight, raw_weight, adjusted_flag)
    """
    area_ellipse = np.pi * width * height  # Ellipse area
    real_weight = area_ellipse * weight_per_pixel  # Raw weight estimate

    if real_weight > 11:
        estimated_weight = 6  # Clamp unrealistic weight to 6 g
        adjusted = True
    else:
        estimated_weight = real_weight
        adjusted = False

    return estimated_weight, real_weight, adjusted

def draw_boxes_with_confidence(image, results):
    total_olives = 0
    img_with_boxes = image.copy()
    for result in results:
        boxes = result.boxes.xyxy
        confs = result.boxes.conf
        total_olives += len(boxes)
        for box, conf in zip(boxes, confs):
            x1, y1, x2, y2 = map(int, box[:4])
            cv2.rectangle(img_with_boxes, (x1, y1), (x2, y2), (255, 0, 0), 2)
            label = f'{conf:.2f}'
            label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
            label_w, label_h = label_size
            cv2.rectangle(img_with_boxes, (x1, y1 - label_h - 10), (x1 + label_w, y1), (255, 0, 0), -1)
            cv2.putText(img_with_boxes, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
    return img_with_boxes, total_olives

def draw_ellipses_and_weight(image, results):
    img_with_ellipses = image.copy()
    total_weight = 0
    actual_weights = []      # Store raw weight estimates (~6 g)
    adjusted_weights = []    # Store clamped weights (set to 6 g)
    adjusted_weight_count = 0  # Counter for clamped weights

    for result in results:
        boxes = result.boxes.xyxy
        for box in boxes:
            x1, y1, x2, y2 = map(int, box[:4])
            width = x2 - x1
            height = y2 - y1

            estimated_weight, real_weight, adjusted = estimate_weight_from_bbox_ellipse(width, height)
            if adjusted:
                adjusted_weight_count += 1
                adjusted_weights.append(estimated_weight)  # All clamped to 6 g
            else:
                actual_weights.append(estimated_weight)

            total_weight += estimated_weight

            center = (x1 + width // 2, y1 + height // 2)
            axes = (width // 2, height // 2)
            cv2.ellipse(img_with_ellipses, center, axes, 0, 0, 360, (0, 0, 255), 2)

            label = f"{estimated_weight:.2f} g"

            # Determine text box size
            label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
            label_w, label_h = label_size

                # Draw the label background for the estimated weight
            cv2.rectangle(img_with_ellipses, (x1, y1 - label_h - 10), (x1 + label_w, y1), (0, 0, 255), -1)
            cv2.putText(img_with_ellipses, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

    return img_with_ellipses, total_weight, actual_weights, adjusted_weights, adjusted_weight_count

def create_mask_with_olive_colors(image, results):
    img_with_mask_colors = image.copy()
    hsv_image = cv2.cvtColor(img_with_mask_colors, cv2.COLOR_BGR2HSV)

    for result in results:
        boxes = result.boxes.xyxy
        for box in boxes:
            x1, y1, x2, y2 = map(int, box[:4])
            width = x2 - x1
            height = y2 - y1
            center = (x1 + width // 2, y1 + height // 2)
            axes = (width // 2, height // 2)

            roi = hsv_image[y1:y2, x1:x2]
            mean_color = cv2.mean(roi)[:3]

            mean_color_bgr = cv2.cvtColor(np.uint8([[mean_color]]), cv2.COLOR_HSV2BGR)[0][0]

            cv2.ellipse(img_with_mask_colors, center, axes, 0, 0, 360, mean_color_bgr.tolist(), -1)
            cv2.ellipse(img_with_mask_colors, center, axes, 0, 0, 360, (0, 0, 0), 2)

    return img_with_mask_colors

def classify_olive_by_gray_intensity(gray_value):
    if gray_value <= 140:
        return "Ripe", (0, 200, 0)
    elif 140 <= gray_value < 180:
        return "Unripe", (0, 165, 255)
    else:
        return "Partially ripe", (0, 255, 255)

def classify_and_fill_colored_contours(image, gray_image, results):
    img_with_filled_ellipses = image.copy()
    ripe_count, partially_ripe_count, unripe_count = 0, 0, 0

    for result in results:
        boxes = result.boxes.xyxy
        for box in boxes:
            x1, y1, x2, y2 = map(int, box[:4])
            width = x2 - x1
            height = y2 - y1
            center = (x1 + width // 2, y1 + height // 2)
            axes = (width // 2, height // 2)

            mask = np.zeros(gray_image.shape, dtype=np.uint8)
            cv2.ellipse(mask, center, axes, 0, 0, 360, 255, -1)
            mean_gray_value = cv2.mean(gray_image, mask=mask)[0]

            maturity_status, fill_color = classify_olive_by_gray_intensity(mean_gray_value)

            cv2.ellipse(img_with_filled_ellipses, center, axes, 0, 0, 360, fill_color, -2)

            if maturity_status == 'Ripe':
                ripe_count += 1
            elif maturity_status == 'Partially ripe':
                partially_ripe_count += 1
            else:
                unripe_count += 1

    return img_with_filled_ellipses, ripe_count, partially_ripe_count, unripe_count

def update_progress(progress_file, current, total):
    progress = {
        'current': current,
        'total': total,
        'percentage': int((current / total) * 100) if total > 0 else 0
    }
    with open(progress_file, 'w') as f:
        json.dump(progress, f)

def process_and_save_results(folder_path, upload_path, progress_file):
    model = load_yolo_model()

    results_folder = os.path.join(folder_path, 'results')
    if not os.path.exists(results_folder):
        os.makedirs(results_folder)

    # Create the 'plot' sub-directory inside 'results'
    plot_folder = os.path.join(results_folder, 'plot')
    if not os.path.exists(plot_folder):
        os.makedirs(plot_folder)

    # Collect the images that need to be processed
    image_filenames = [f for f in os.listdir(upload_path) if f.endswith(('.jpg', '.png', '.jpeg'))]
    total_images = len(image_filenames)
    current_image_index = 0

    # Initialize progress tracking
    update_progress(progress_file, current_image_index, total_images)

    summary_results = {
        "total_olives": 0,
        "total_weight_approx": 0,  # Sum of detected olive weights
        "average_weight_per_olive": 6,  # Average olive weight in grams
        "images": [],
        "ripe_total": 0,
        "partially_ripe_total": 0,
        "unripe_total": 0,
        "adjusted_weight_count": 0  # Total olives with a clamped weight
    }
    weights_all_images = []
    adjusted_weights_all_images = []  # Store clamped weights
    ripe_total, partially_ripe_total, unripe_total = 0, 0, 0
    total_adjusted_weight_count = 0  # Track total clamped weights

    for idx, filename in enumerate(image_filenames):
        current_image_index += 1

        image_path = os.path.join(upload_path, filename)
        print(f"Processing {image_path}...")

        image = load_image(image_path)
        enhanced_image = enhance_image(image)
        results = run_yolo_inference(model, image_path, conf=0.5)

        img_boxes_conf, total_olives = draw_boxes_with_confidence(image, results)
        img_ellipses, total_weight, actual_weights, adjusted_weights, adjusted_weight_count = draw_ellipses_and_weight(image, results)
        total_adjusted_weight_count += adjusted_weight_count  # Update overall count of clamped weights

        mask_colors = create_mask_with_olive_colors(enhanced_image, results)

        gray_image = cv2.cvtColor(enhanced_image, cv2.COLOR_BGR2GRAY)
        img_maturity, ripe_count, partially_ripe_count, unripe_count = classify_and_fill_colored_contours(mask_colors, gray_image, results)

        # Update counters for maturity categories
        ripe_total += ripe_count
        partially_ripe_total += partially_ripe_count
        unripe_total += unripe_count

        # Store per-image metrics
        summary_results["images"].append({
            "filename": filename,
            "total_olives": total_olives,
            "total_weight": total_weight,
            "adjusted_weight_count": adjusted_weight_count  # Number of clamped weights in this image
        })

        weights_all_images.extend(actual_weights)
        adjusted_weights_all_images.extend(adjusted_weights)

        # Render the three pipeline stages side by side
        fig, axs = plt.subplots(1, 3, figsize=(7, 3))

        # Style figure and subplot backgrounds
        figure_background_color = '#F2F5D8'  # Light cream for the outside background
        axes_background_color = 'white'  # White background for inner plots

        fig.patch.set_facecolor(figure_background_color)
        for ax in axs:
            ax.set_facecolor(axes_background_color)

        # Compute margins (normalized units) to emulate roughly an 8 mm border
        left_margin = 0.315 / 10  # Left margin (0.315 inches on a 10 inch width)
        right_margin = 1 - (0.315 / 10)  # Right margin
        top_margin = 1 - (0.315 / 2.5)  # Top margin (0.315 inches on a 2.5 inch height)
        bottom_margin = 0.315 / 2.5  # Bottom margin

        plt.subplots_adjust(
            left=left_margin,
            right=right_margin,
            top=top_margin,
            bottom=bottom_margin,
            wspace=0.05  # Space between subplots
        )

        # Track the current image number
        image_number = idx + 1

        # Update subplot titles with the running index
        axs[0].imshow(cv2.cvtColor(img_boxes_conf, cv2.COLOR_BGR2RGB))
        axs[0].set_title(f"Detected olives: {total_olives}")
        axs[1].imshow(cv2.cvtColor(img_ellipses, cv2.COLOR_BGR2RGB))
        axs[1].set_title(f"Total weight: {total_weight:.2f} g")
        axs[2].imshow(cv2.cvtColor(img_maturity, cv2.COLOR_BGR2RGB))
        axs[2].set_title("Maturity")

        for ax in axs:
            ax.axis('off')
            # Match subplot border colors with the background
            for spine in ax.spines.values():
                spine.set_edgecolor(figure_background_color)

        # Save the subplot montage directly in the 'results' folder
        subplot_filename = os.path.join(results_folder, f'{os.path.splitext(filename)[0]}_pipeline.jpg')
        plt.savefig(subplot_filename, dpi=300, facecolor=fig.get_facecolor(), edgecolor='none', bbox_inches='tight')  # Save with the custom background
        plt.close()

        print(f"Completed {filename}")

        # Update the progress tracker after processing the image
        update_progress(progress_file, current_image_index, total_images)

    # Update aggregated summary results
    total_olives_sum = sum(img["total_olives"] for img in summary_results["images"])
    total_weight_approx = sum(img["total_weight"] for img in summary_results["images"])
    total_adjusted_weight_count = sum(img["adjusted_weight_count"] for img in summary_results["images"])

    summary_results["total_olives"] = total_olives_sum
    summary_results["total_weight_approx"] = total_weight_approx
    summary_results["adjusted_weight_count"] = total_adjusted_weight_count

    # Compute the total weight estimate using the fixed-per-olive average
    average_weight_per_olive = summary_results["average_weight_per_olive"]
    total_weight_average = total_olives_sum * average_weight_per_olive
    summary_results["total_weight_average"] = total_weight_average

    summary_results["average_weight"] = summary_results["total_weight_approx"] / total_olives_sum if total_olives_sum > 0 else 0
    summary_results["ripe_total"] = ripe_total
    summary_results["partially_ripe_total"] = partially_ripe_total
    summary_results["unripe_total"] = unripe_total

    # Plot the distribution of olive maturity
    categories = ['Fully ripe', 'Partially ripe', 'Unripe']
    counts = [ripe_total, partially_ripe_total, unripe_total]
    colors = ['lightgreen', 'yellow', 'orange']

    plt.figure(figsize=(6, 5))  # Set figure size
    plt.rcParams['figure.facecolor'] = '#F2F5D8'  # Outer background color
    plt.rcParams['axes.facecolor'] = 'white'  # Inner background color
    plt.rcParams['savefig.facecolor'] = '#F2F5D8'  # Outer background for saving

    bars = plt.bar(categories, counts, color=colors, edgecolor='black')

    for bar, count in zip(bars, counts):
        plt.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                 f'{count}', ha='center', fontsize=10, color='black')

    plt.title('Olive maturity distribution')
    plt.xlabel('Maturity level')
    plt.ylabel('Number of olives')
    plt.tight_layout()
    plt.savefig(os.path.join(plot_folder, 'olive_maturity_distribution.png'), dpi=300)
    plt.close()

    # Plot the distribution of olive weights
    plt.figure(figsize=(6, 5))
    plt.rcParams['figure.facecolor'] = '#F2F5D8'  # Outer background color
    plt.rcParams['axes.facecolor'] = 'white'  # Inner background color
    plt.rcParams['savefig.facecolor'] = '#F2F5D8'  # Outer background for saving

    if len(weights_all_images) > 0 or len(adjusted_weights_all_images) > 0:
        # Define shared bins for both distributions
        all_weights = weights_all_images + adjusted_weights_all_images
        bins = np.linspace(0, max(all_weights) + 1, 20)

        # Histogram for raw weights
        plt.hist(weights_all_images, bins=bins, color='green', edgecolor='black', label='Raw weight ~6 g')

        # Histogram for clamped weights (semi-transparent)
        plt.hist(adjusted_weights_all_images, bins=bins, color='green', edgecolor='black', alpha=0.5, label='Clamped weight (6 g)')

        plt.legend()
    else:
        plt.text(0.5, 0.5, 'No data available', horizontalalignment='center', verticalalignment='center', transform=plt.gca().transAxes)

    plt.title('Olive weight distribution')
    plt.xlabel('Weight (g)')
    plt.ylabel('Number of olives')
    plt.tight_layout()
    plt.savefig(os.path.join(plot_folder, 'olive_weight_distribution.png'), dpi=300)
    plt.close()

    # Save summary metrics as JSON
    summary_file_path = os.path.join(results_folder, 'summary_results.json')
    with open(summary_file_path, 'w') as summary_file:
        json.dump(summary_results, summary_file, indent=4)

    print("Summary results saved successfully.")

# Run as standalone script
if __name__ == '__main__':
    folder_path = os.path.abspath(os.path.dirname(__file__))
    upload_path = os.path.join(folder_path, 'upload')
    progress_file = os.path.join(folder_path, 'progress.json')

    # Reset progress to zero


    process_and_save_results(folder_path, upload_path, progress_file)
