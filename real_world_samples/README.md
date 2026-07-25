# Real-World Furniture Image Samples

This folder contains 50 manually reviewed photographs of real indoor environments for testing the MoveAI prototype. Unlike the earlier HomeObjects-3K selection, these images were checked to exclude obvious CGI renders, drawings, and illustrations.

## Source

- Dataset: Open Images validation set
- Project page: https://storage.googleapis.com/openimages/web/index.html
- Annotations: CC BY 4.0
- Images: listed by Open Images as CC BY 2.0

Open Images advises users to verify each image's individual license. The per-image author, license URL, title, and original landing page are recorded in `manifest.csv`.

## What is represented

- occupied and unoccupied bedrooms
- ordinary living rooms
- kitchens and dining areas
- beds, sofas, tables, desks, cabinets, drawers, refrigerators, and washing machines
- clutter, occlusion, uneven lighting, narrow views, and varied camera angles
- older and newer household interiors

## Folder contents

- `images/`: 50 real-world photographs numbered `001` to `050`
- `contact_sheets/`: two sheets for quick visual review
- `manifest.csv`: image IDs, furniture annotations, titles, authors, licenses, and source links

## Evaluation note

These images are suitable for comparing zero-shot furniture detectors. If Open Images is later used for training or fine-tuning, create a separate independent test set before reporting model performance.
