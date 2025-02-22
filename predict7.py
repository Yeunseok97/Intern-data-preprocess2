# Ultralytics YOLOv5 🚀, AGPL-3.0 license
"""
Run YOLOv5 segmentation inference on images, videos, directories, streams, etc.

Usage - sources:
    $ python segment/predict.py --weights yolov5s-seg.pt --source 0                               # webcam
                                                                  img.jpg                         # image
                                                                  vid.mp4                         # video
                                                                  screen                          # screenshot
                                                                  path/                           # directory
                                                                  list.txt                        # list of images
                                                                  list.streams                    # list of streams
                                                                  'path/*.jpg'                    # glob
                                                                  'https://youtu.be/LNwODJXcvt4'  # YouTube
                                                                  'rtsp://example.com/media.mp4'  # RTSP, RTMP, HTTP stream

Usage - formats:
    $ python segment/predict.py --weights yolov5s-seg.pt                 # PyTorch
                                          yolov5s-seg.torchscript        # TorchScript
                                          yolov5s-seg.onnx               # ONNX Runtime or OpenCV DNN with --dnn
                                          yolov5s-seg_openvino_model     # OpenVINO
                                          yolov5s-seg.engine             # TensorRT
                                          yolov5s-seg.mlmodel            # CoreML (macOS-only)
                                          yolov5s-seg_saved_model        # TensorFlow SavedModel
                                          yolov5s-seg.pb                 # TensorFlow GraphDef
                                          yolov5s-seg.tflite             # TensorFlow Lite
                                          yolov5s-seg_edgetpu.tflite     # TensorFlow Edge TPU
                                          yolov5s-seg_paddle_model       # PaddlePaddle
"""
import pandas as pd
import argparse
import os
import platform
import sys
from pathlib import Path
import torch
import numpy as np
import cv2


FILE = Path(__file__).resolve()
ROOT = FILE.parents[1]  # YOLOv5 root directory
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))  # add ROOT to PATH
ROOT = Path(os.path.relpath(ROOT, Path.cwd()))  # relative

from ultralytics.utils.plotting import Annotator, colors, save_one_box

from models.common import DetectMultiBackend
from utils.dataloaders import IMG_FORMATS, VID_FORMATS, LoadImages, LoadScreenshots, LoadStreams
from utils.general import (
    LOGGER,
    Profile,
    check_file,
    check_img_size,
    check_imshow,
    check_requirements,
    colorstr,
    cv2,
    increment_path,
    non_max_suppression,
    print_args,
    scale_boxes,
    scale_segments,
    strip_optimizer,
)
from utils.segment.general import masks2segments, process_mask, process_mask_native
from utils.torch_utils import select_device, smart_inference_mode

def upscale_image(image, scale_factor):
    # 이미지 업스케일링
    height, width = image.shape[:2]
    new_size = (width * scale_factor, height * scale_factor)
    upscaled_image = cv2.resize(image, new_size, interpolation=cv2.INTER_LINEAR)
    return upscaled_image

@smart_inference_mode()
def run(
    weights=ROOT / "yolov5s-seg.pt",  # model.pt path(s)
    source=ROOT / "data/images",  # file/dir/URL/glob/screen/0(webcam)
    data=ROOT / "data/coco128.yaml",  # dataset.yaml path
    imgsz=(640, 640),  # inference size (height, width)
    conf_thres=0.25,  # confidence threshold
    iou_thres=0.45,  # NMS IOU threshold
    max_det=1000,  # maximum detections per image
    device="",  # cuda device, i.e. 0 or 0,1,2,3 or cpu
    view_img=False,  # show results
    save_txt=False,  # save results to *.txt
    save_conf=False,  # save confidences in --save-txt labels
    save_crop=False,  # save cropped prediction boxes
    nosave=False,  # do not save images/videos
    classes=None,  # filter by class: --class 0, or --class 0 2 3
    agnostic_nms=False,  # class-agnostic NMS
    augment=False,  # augmented inference
    visualize=False,  # visualize features
    update=False,  # update all models
    project=ROOT / "runs/predict-seg",  # save results to project/name
    name="exp",  # save results to project/name
    exist_ok=False,  # existing project/name ok, do not increment
    line_thickness=3,  # bounding box thickness (pixels)
    hide_labels=False,  # hide labels
    hide_conf=False,  # hide confidences
    half=False,  # use FP16 half-precision inference
    dnn=False,  # use OpenCV DNN for ONNX inference
    vid_stride=1,  # video frame-rate stride
    retina_masks=False,
):
    """Run YOLOv5 segmentation inference on diverse sources including images, videos, directories, and streams."""
    source = str(source)
    save_img = not nosave and not source.endswith(".txt")  # save inference images
    is_file = Path(source).suffix[1:] in (IMG_FORMATS + VID_FORMATS)
    is_url = source.lower().startswith(("rtsp://", "rtmp://", "http://", "https://"))
    webcam = source.isnumeric() or source.endswith(".streams") or (is_url and not is_file)
    screenshot = source.lower().startswith("screen")
    if is_url and is_file:
        source = check_file(source)  # download

    # Directories
    save_dir = increment_path(Path(project) / name, exist_ok=exist_ok)  # increment run
    (save_dir / "labels" if save_txt else save_dir).mkdir(parents=True, exist_ok=True)  # make dir

    # Load model
    device = select_device(device)
    model = DetectMultiBackend(weights, device=device, dnn=dnn, data=data, fp16=half)
    stride, names, pt = model.stride, model.names, model.pt
    imgsz = check_img_size(imgsz, s=stride)  # check image size

    # Dataloader
    bs = 1  # batch_size
    if webcam:
        view_img = check_imshow(warn=True)
        dataset = LoadStreams(source, img_size=imgsz, stride=stride, auto=pt, vid_stride=vid_stride)
        bs = len(dataset)
    elif screenshot:
        dataset = LoadScreenshots(source, img_size=imgsz, stride=stride, auto=pt)
    else:
        dataset = LoadImages(source, img_size=imgsz, stride=stride, auto=pt, vid_stride=vid_stride)
    vid_path, vid_writer = [None] * bs, [None] * bs

    # Run inference
    model.warmup(imgsz=(1 if pt else bs, 3, *imgsz))  # warmup
    seen, windows, dt = 0, [], (Profile(device=device), Profile(device=device), Profile(device=device))
    df = pd.DataFrame(columns=["File_name", "Scaled","Success", "Note","Current_pixel"])

    for path, im, im0s, vid_cap, s in dataset:
        with dt[0]:
            im = torch.from_numpy(im).to(model.device)
            im = im.half() if model.fp16 else im.float()  # uint8 to fp16/32
            im /= 255  # 0 - 255 to 0.0 - 1.0
            if len(im.shape) == 3:
                im = im[None]  # expand for batch dim

        # Inference
        with dt[1]:
            visualize = increment_path(save_dir / Path(path).stem, mkdir=True) if visualize else False
            pred, proto = model(im, augment=augment, visualize=visualize)[:2]

        # NMS
        with dt[2]:
            pred = non_max_suppression(pred, conf_thres, iou_thres, classes, agnostic_nms, max_det=max_det, nm=32)

        # Second-stage classifier (optional)
        # pred = utils.general.apply_classifier(pred, classifier_model, im, im0s)


        # Initialize person variable
        person_counter = 0
        half_class_success_path = Path('/home/selectstar/yolov5/runs/half_class_success_path')
        full_success_path = Path('/home/selectstar/yolov5/runs/full_success_path')
        failed_path = Path('/home/selectstar/yolov5/runs/class_height_failed')

        scale_factor =2 
        results = {}
        
        # Create directories if they don't exist
        # success_path.mkdir(parents=True, exist_ok=True)
        
        half_class_success_path.mkdir(parents=True, exist_ok=True)
        full_success_path.mkdir(parents=True, exist_ok=True)
        failed_path.mkdir(parents=True, exist_ok=True)

        
        # Process predictions
        for i, det in enumerate(pred):  # per image
            seen += 1
            if webcam:  # batch_size >= 1
                p, im0, frame = path[i], im0s[i].copy(), dataset.count
                s += f"{i}: "
            else:
                p, im0, frame = path, im0s.copy(), getattr(dataset, "frame", 0)

            p = Path(p)  # to Path
            file_name = p.stem
            is_full = "Full" in file_name
            is_half = "Half" in file_name
            success = ""
            save_path = str(save_dir / p.name)  # im.jpg
            
            image_width, image_height = im0.shape[1], im0.shape[0]
            image_size = image_width * image_height
            
            txt_path = str(save_dir / "labels" / p.stem) + ("" if dataset.mode == "image" else f"_{frame}")  # im.txt
            s += "%gx%g " % im.shape[2:]  # print string
            imc = im0.copy() if save_crop else im0  # for save_crop
            annotator = Annotator(im0, line_width=line_thickness, example=str(names))

            original_im0 = im0.copy()

            if len(det):
                if retina_masks:
                    # Scale bbox first then crop masks
                    det[:, :4] = scale_boxes(im.shape[2:], det[:, :4], im0.shape).round()  # Rescale boxes to im0 size
                    masks = process_mask_native(proto[i], det[:, 6:], det[:, :4], im0.shape[:2])  # HWC
                else:
                    masks = process_mask(proto[i], det[:, 6:], det[:, :4], im.shape[2:], upsample=True)  # HWC
                    det[:, :4] = scale_boxes(im.shape[2:], det[:, :4], im0.shape).round()  # Rescale boxes to im0 size

        # Segments
                if save_txt:
                    segments = [
                        scale_segments(im0.shape if retina_masks else im.shape[2:], x, im0.shape, normalize=True)
                        for x in reversed(masks2segments(masks))
                    ]

        # Print results
                excluded_classes = ["bird", "cat", "dog", "horse", "cow", "elephant", "bear", "zebra", "giraffe",]
                excluded_count = 0
                for c in det[:, 5].unique():
                    n = (det[:, 5] == c).sum()  # Detections per class
                    s += f"{n} {names[int(c)]}{'s' * (n > 1)}, "  # Add to string
                    if names[int(c)] == "person":
                        person_counter += n  # Increment person counter
                    elif names[int(c)] in excluded_classes:
                        excluded_count += n

                # Mask plotting
                annotator.masks(
                    masks,
                    colors=[colors(x, True) for x in det[:, 5]],
                    im_gpu=torch.as_tensor(im0, dtype=torch.float16).to(device).permute(2, 0, 1).flip(0).contiguous() / 255 if retina_masks else im[i],
        )
                image_height = im0.shape[0]
        
        # Write results
                segment_data_list = []
                for j, (*xyxy, conf, cls) in enumerate(reversed(det[:, :6])):
                    if save_txt:  # Save to JSON
                        if names[int(cls)] == "person":
                            seg = segments[j].reshape(-1)  # (n,2) to (n*2)
                            segment_list = [seg[i:i+2].tolist() for i in range(0, len(seg), 2)]  # Convert to list of [x, y] pairs
                            segment_data = {
                                'class': int(cls),
                                'confidence': conf.item(),
                                'polygon': segment_list
                            }
                            segment_data_list.append(segment_data)
                            
                    # Calculate y min and max
                        if segment_data_list:
                            y_values = [point[1] for point in segment_list]
                            y_min = min(y_values)
                            y_max = max(y_values)
                            y_min_pixel = y_min * image_height  # Convert to pixel
                            y_max_pixel = y_max * image_height  # Convert to pixel

            # Stream results
            im0 = annotator.result()
            if view_img:
                if platform.system() == "Linux" and p not in windows:
                    windows.append(p)
                    cv2.namedWindow(str(p), cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO)  # Allow window resize (Linux)
                    cv2.resizeWindow(str(p), im0.shape[1], im0.shape[0])
                cv2.imshow(str(p), im0)
                if cv2.waitKey(1) == ord("q"):  # 1 millisecond
                    exit()

            # Save results (image with detections)
            if save_img:
                if dataset.mode == "image":
                    cv2.imwrite(save_path, im0)
                else:  # 'video' or 'stream'
                    if vid_path[i] != save_path:  # New video
                        vid_path[i] = save_path
                        if isinstance(vid_writer[i], cv2.VideoWriter):
                            vid_writer[i].release()  # Release previous video writer
                        if vid_cap:  # Video
                            fps = vid_cap.get(cv2.CAP_PROP_FPS)
                            w = int(vid_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                            h = int(vid_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        else:  # Stream
                            fps, w, h = 30, im0.shape[1], im0.shape[0]
                        save_path = str(Path(save_path).with_suffix(".mp4"))  # Force *.mp4 suffix on results videos
                        vid_writer[i] = cv2.VideoWriter(save_path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
                    vid_writer[i].write(im0)
            
            
            # Process1 조건 ㅎㅎ
            # class 확인
            if person_counter == 1 and excluded_count == 0:
                
            #원본 사이즈 조건 확인
                if image_size>= 8200000:
                    
                    # Full의 경우 높이 조건을 추가로 검사
                    if is_full:
                        if (y_max_pixel - y_min_pixel) >= image_height / 2:
                            LOGGER.info(f"{s}{'' if len(det) else '(no detections), '}{dt[1].dt * 1E3:.1f}ms")
                            print("Full file Condition Success!!! \n")
                            save_custom = full_success_path / f"{p.stem}.png"
                            success = "O"
                            Note = "-"
                            Scaled = "X"
                            Current_pixel = str(image_size)
                        else:
                            print(f"image condition: {image_height / 2}, person height: {y_max_pixel - y_min_pixel}")
                            LOGGER.info(f"{s}{'' if len(det) else '(no detections), '}{dt[1].dt * 1E3:.1f}ms")
                            print("height condition failed!!!!\n\n")
                            save_custom = failed_path / f"{p.stem}.png"

                            success = "X"
                            Note = "height failed"
                            Scaled = "X"
                            Current_pixel = str(image_size)
                    elif is_half:    # Half의 경우 높이 조건 없이 성공 처리
                    
                        LOGGER.info(f"{s}{'' if len(det) else '(no detections), '}{dt[1].dt * 1E3:.1f}ms")
                        print("Half file condition Success!!! \n")
                        save_custom = half_class_success_path / f"{p.stem}.png"

                        success = "O"
                        Note = "-"
                        Scaled = "X"
                        Current_pixel = str(image_size)
                # 820만 픽셀 미만일 경우, 스케일링 필요여부 확인
                else:
                    if image_size * scale_factor**2 >= 8200000:
                    
                    
                        if is_half:
                            upscaled_im0 = upscale_image(im0, scale_factor)
                            upscaled_width, upscaled_height = upscaled_im0.shape[1], upscaled_im0.shape[0]
                            scaled_size = upscaled_width * upscaled_height
                            LOGGER.info(f"{s}{'' if len(det) else '(no detections), '}{dt[1].dt * 1E3:.1f}ms")
                            print("Condition Success after upscaling!!! \n")
                            save_custom = half_class_success_path / f"{p.stem}_scaled.png"
                            success = "O"
                            Note = "-"
                            Scaled = "O"
                            Current_pixel = str(scaled_size)
                        # Full 이미지에 대해 높이 조건 통과 후 업스케일링
                        elif is_full:
                            
                            if (y_max_pixel - y_min_pixel) >= (upscaled_height / 2):

                                upscaled_im0 = upscale_image(im0, scale_factor)
                                upscaled_width, upscaled_height = upscaled_im0.shape[1], upscaled_im0.shape[0]
                                scaled_size = upscaled_width * upscaled_height
                                LOGGER.info(f"{s}{'' if len(det) else '(no detections), '}{dt[1].dt * 1E3:.1f}ms")
                                print("Condition Success after upscaling!!! \n")
                                save_custom = full_success_path / f"{p.stem}_scaled.png"
                                success = "O"
                                Note = "-"
                                Scaled = "O"
                                Current_pixel = str(scaled_size)
                            
                            else:
                                LOGGER.info(f"{s}{'' if len(det) else '(no detections), '}{dt[1].dt * 1E3:.1f}ms")
                                print(f"height condition failed after upscaling!!!!\n\n")
                                save_custom = failed_path / f"{p.stem}_scaled.png"
                                success = "X"
                                Note = "height failed"
                                Scaled = "X"
                                Current_pixel = str(image_size)
                    
                    else: # 2스케일링 해도 820만 픽셀 미만일 경우
                        LOGGER.info(f"{s}{'' if len(det) else '(no detections), '}{dt[1].dt * 1E3:.1f}ms")
                        print(f"size condition failed!!!!\n\n")
                        save_custom = failed_path / f"{p.stem}_scaled_failed.png"
                        success = "X"
                        Note = "Size failed"
                        Scaled = "X"
                        Current_pixel = str(image_size)
                        
            else:  # 클래스 조건 실패 시
        
                print(f"failed person count: {person_counter}")
                LOGGER.info(f"{s}{'' if len(det) else '(no detections), '}{dt[1].dt * 1E3:.1f}ms")
                print("class condition failed!!!!\n\n")
                save_custom = failed_path / f"{p.name}.png"
                # print("Final save dir", save_custom) -> log 확인 용
                success = "X"
                Note = "class failed"
                Scaled = "X"
                
            
            cv2.imwrite(str(save_custom), original_im0)
            
            results[file_name] = success
            current_result = pd.DataFrame([[file_name, Scaled, success, Note, Current_pixel ]], columns=["File_name", "Scaled","Success","Note","Current_pixel"])
            # print("current_result", current_result) -> log
            print()
            df = pd.concat([df, current_result], ignore_index=True)
            print()
            failed_file_list = df[df["Success"] =="X"]
            
            # print(df) -> log

    # Step 3: After processing all images, save the DataFrame to a CSV file
    csv_file_path = '/home/selectstar/yolov5/runs/class_height_whole_files.csv'  # 원하는 CSV 파일 경로로 변경
    csv_file_path1 = '/home/selectstar/yolov5/runs/class_height_failed_files.csv'
    df.to_csv(csv_file_path, index=False, encoding='utf-8-sig')
    failed_file_list.to_csv(csv_file_path1, index=False, encoding='utf-8-sig')
    
    # Print results
    t = tuple(x.t / seen * 1e3 for x in dt)  # speeds per image
    LOGGER.info(f"Speed: %.1fms pre-process, %.1fms inference, %.1fms NMS per image at shape {(1, 3, *imgsz)}" % t)
    if save_txt or save_img:
        s = f"\n{len(list(save_dir.glob('labels/*.txt')))} labels saved to {save_dir / 'labels'}" if save_txt else ""
        LOGGER.info(f"Results saved to {colorstr('bold', save_dir)}{s}")
    if update:
        strip_optimizer(weights[0])  # update model (to fix SourceChangeWarning)


def parse_opt():
    """Parses command-line options for YOLOv5 inference including model paths, data sources, inference settings, and
    output preferences.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", nargs="+", type=str, default=ROOT / "yolov5s-seg.pt", help="model path(s)")
    parser.add_argument("--source", type=str, default=ROOT / "data/images", help="file/dir/URL/glob/screen/0(webcam)")
    parser.add_argument("--data", type=str, default=ROOT / "data/coco128.yaml", help="(optional) dataset.yaml path")
    parser.add_argument("--imgsz", "--img", "--img-size", nargs="+", type=int, default=[640], help="inference size h,w")
    parser.add_argument("--conf-thres", type=float, default=0.25, help="confidence threshold")
    parser.add_argument("--iou-thres", type=float, default=0.45, help="NMS IoU threshold")
    parser.add_argument("--max-det", type=int, default=1000, help="maximum detections per image")
    parser.add_argument("--device", default="", help="cuda device, i.e. 0 or 0,1,2,3 or cpu")
    parser.add_argument("--view-img", action="store_true", help="show results")
    parser.add_argument("--save-txt", action="store_true", help="save results to *.txt")
    parser.add_argument("--save-conf", action="store_true", help="save confidences in --save-txt labels")
    parser.add_argument("--save-crop", action="store_true", help="save cropped prediction boxes")
    parser.add_argument("--nosave", action="store_true", help="do not save images/videos")
    parser.add_argument("--classes", nargs="+", type=int, help="filter by class: --classes 0, or --classes 0 2 3")
    parser.add_argument("--agnostic-nms", action="store_true", help="class-agnostic NMS")
    parser.add_argument("--augment", action="store_true", help="augmented inference")
    parser.add_argument("--visualize", action="store_true", help="visualize features")
    parser.add_argument("--update", action="store_true", help="update all models")
    parser.add_argument("--project", default=ROOT / "runs/predict-seg", help="save results to project/name")
    parser.add_argument("--name", default="exp", help="save results to project/name")
    parser.add_argument("--exist-ok", action="store_true", help="existing project/name ok, do not increment")
    parser.add_argument("--line-thickness", default=3, type=int, help="bounding box thickness (pixels)")
    parser.add_argument("--hide-labels", default=False, action="store_true", help="hide labels")
    parser.add_argument("--hide-conf", default=False, action="store_true", help="hide confidences")
    parser.add_argument("--half", action="store_true", help="use FP16 half-precision inference")
    parser.add_argument("--dnn", action="store_true", help="use OpenCV DNN for ONNX inference")
    parser.add_argument("--vid-stride", type=int, default=1, help="video frame-rate stride")
    parser.add_argument("--retina-masks", action="store_true", help="whether to plot masks in native resolution")
    opt = parser.parse_args()
    opt.imgsz *= 2 if len(opt.imgsz) == 1 else 1  # expand
    print_args(vars(opt))
    return opt


def main(opt):
    """Executes YOLOv5 model inference with given options, checking for requirements before launching."""
    check_requirements(ROOT / "requirements.txt", exclude=("tensorboard", "thop"))
    run(**vars(opt))


if __name__ == "__main__":
    opt = parse_opt()
    main(opt)
