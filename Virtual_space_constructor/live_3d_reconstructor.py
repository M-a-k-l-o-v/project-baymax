#imports 
import cv2
import torch
import numpy as np
import open3d as o3d
import collections

#loading image proceesing model midas
device = "mps" if torch.backends.mps.is_available() else "cpu" # tries to use gpu if availiable else uses cpu

depth_model = torch.hub.load("intel-isl/MiDaS", "DPT_Large")
depth_model.to(device)
depth_model.eval()

transform = torch.hub.load("intel-isl/MiDaS", "transforms").dpt_transform #defines the function to transforms image into a form for MIDAS' depth prediction models(transformation includes file type btw) and moves it to the gpu for inference

def clear_all():
    import torch, gc, cv2
    torch.cuda.empty_cache()
    gc.collect()
    cv2.destroyAllWindows()

def get_depth_map(rgb_frame):
    rgb_image = cv2.cvtColor(rgb_frame, cv2.COLOR_BGR2RGB).astype(np.float32) # Convert from BGR(blue - green - red) (OpenCV default) to RGB for midas
    
    # Apply MiDaS transform (returns tensor)
    transformed = transform(rgb_image) # normalised for midas so image/255
    input_tensor = transformed.to(device)

    with torch.no_grad(): # this is an evalution so there is no need to waste processing power on gradient calculation for the weights
        depth_prediction = depth_model(input_tensor) 
    
        depth_prediction = torch.nn.functional.interpolate( #to resize the depth map to the camera resolution 
            depth_prediction.unsqueeze(1), # the depth_prediction is 3D but the interpolation function expects a 4D form we unsqueez
            size=rgb_image.shape[:2],
            mode="bicubic",
            align_corners=False,
        ).squeeze()

        depth_map = depth_prediction.squeeze().cpu().numpy() # needs to be renomalised for opencv which is done below

        depth_vis = cv2.normalize(depth_map, None, 0, 255, cv2.NORM_MINMAX)
        depth_vis = depth_vis.astype(np.uint8)
        depth_color = cv2.applyColorMap(depth_vis, cv2.COLORMAP_MAGMA)

        cv2.imshow("Depth Map", depth_color)
        cv2.waitKey(1)

    return depth_map, rgb_image # Return both!

def depth_to_3d_points_with_color(depth_map, rgb_image, focal_length=500): # ill need to adjust this focal length to be calibrated with open cv not a fixed number
    height, width = depth_map.shape
    center_x, center_y = width / 2, height / 2
    y_indices, x_indices = np.indices((height, width))

    Z = depth_map
    X = (x_indices - center_x) * Z / focal_length
    Y = (y_indices - center_y) * Z / focal_length

    points_3d = np.stack((X, Y, Z), axis=-1).reshape(-1, 3)
    colors  = rgb_image.reshape(-1, 3) / 255.0  # Normalize to 0-1
    return points_3d, colors

def manual_capture_reconstruction():
    camera = cv2.VideoCapture(0)
    #camera.set(cv2.CAP_PROP_FRAME_WIDTH,640) #change resolusion to 360p to reduce processing power required for live 
    #camera.set(cv2.CAP_PROP_FRAME_HEIGHT,360)

    scene_points = o3d.geometry.PointCloud()
    visualizer = o3d.visualization.Visualizer()
    visualizer.create_window("Live 3D Scene", width=800, height=600)
    visualizer.add_geometry(scene_points)

    voxel_size = 0.02
    capture_count = 0
    visualizer = None

    print("=== Manual Capture Mode ===")
    print("SPACEBAR - Capture frame")
    print("ESC - Finish and save")
    print("\nPosition camera and press SPACEBAR when ready...")


    while True:
        success, frame = camera.read()
        if not success:
            break

        # Show live preview with instructions
        preview = frame.copy()
        cv2.putText(preview, f"Captures: {capture_count}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.putText(preview, "SPACE=Capture ESC=Done", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        cv2.imshow("Camera Preview", preview)

        key = cv2.waitKey(1)

        # Spacebar pressed - capture!
        if key == 32:  # Spacebar
            print(f"\n[Capture {capture_count + 1}] Processing...")
                
            # Depth estimation and conversion
            depth_map, rgb_image  = get_depth_map(frame)
            new_points, new_colors = depth_to_3d_points_with_color(depth_map, rgb_image)

            # Filter out extreme depth values (common noise)
            valid_mask = (depth_map.flatten() > 0.5) & (depth_map.flatten() < 10)
            new_points = new_points[valid_mask]
            new_colors = new_colors[valid_mask]

            # Build Open3D cloud with colour
            new_cloud = o3d.geometry.PointCloud()
            new_cloud.points = o3d.utility.Vector3dVector(new_points)
            new_cloud.colors = o3d.utility.Vector3dVector(new_colors)

            # Statistical outlier removal (reduces noise!)
            new_cloud, _ = new_cloud.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)

            if len(scene_points.points) == 0:
                # First capture - just add it
                scene_points = new_cloud
            else: # align the new scene with the old one using ICP, which finds the best transformation( using rotation or translation) to align the new and old scenes
                 threshold = 0.02 # distance threshold, the maximum distamce to considered a point   match 
                 intial_transformation = np.identity(4)

                 reg = o3d.pipelines.registration.registration_icp(
                 new_cloud, scene_points, threshold, intial_transformation,
                 o3d.pipelines.registration.TransformationEstimationPointToPoint(),
                 o3d.pipelines.registration.ICPConvergenceCriteria(max_iteration=50)
                )
                 
                 # Apply transformation to align
                 new_cloud.transform(reg.transformation)
                 scene_points += new_cloud

            scene_points = scene_points.voxel_down_sample(voxel_size)

            # Create visualizer after first capture
            if visualizer is None:
                print("Creating 3D visualizer window...")
                visualizer = o3d.visualization.Visualizer()
                visualizer.create_window("3D Scene", width=1000, height=800)
                visualizer.add_geometry(scene_points)
            else:
                visualizer.clear_geometries()
                visualizer.add_geometry(scene_points)
                visualizer.reset_view_point(True)
            
            capture_count += 1
            print(f"✓ Added to scene. Total points: {len(scene_points.points)}")

        # ESC pressed - finish
        if key == 27:
            break

        if visualizer is not None:
            visualizer.poll_events()
            visualizer.update_renderer()

    camera.release()
    cv2.destroyAllWindows()
                
    if len(scene_points.points) > 0:
        o3d.io.write_point_cloud("scanned_scene.ply", scene_points)
        print(f"\n✓ Saved to 'scanned_scene.ply'")
        o3d.visualization.draw_geometries([scene_points], 
                                         window_name="Final 3D Scan",
                                         width=1000, height=800)
    
    return scene_points
    

    
    




