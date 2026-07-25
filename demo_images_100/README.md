# Demo Image Review Set

This folder contains 100 real indoor photographs selected for testing large-furniture detection in the MoveAI prototype.

## Source and license

- Dataset: HomeObjects-3K by Ultralytics
- Source: https://docs.ultralytics.com/datasets/detect/homeobjects-3k/
- License: AGPL-3.0
- Split used: validation only

Retain this attribution when using the images in the prototype or presentation.

## Selection strategy

The set is intentionally biased toward large items relevant to home moving and furniture disposal:

- bed
- sofa
- table
- television
- wardrobe

It also includes chairs, lamps, doors, windows, plants, laptops, and photo frames as surrounding context and possible distractors. Images include bedrooms, living rooms, dining areas, different lighting conditions, partial views, crowded rooms, and multi-object scenes.

## Folder contents

- `images/`: exactly 100 photographs, prefixed with review IDs `001` to `100`.
- `annotations/`: original YOLO-format ground-truth labels, renamed to match each image.
- `contact_sheets/`: four sheets showing 25 images each for fast review.
- `manifest.csv`: source filename, known classes, large-item classes, and annotation count.

## Class IDs in annotation files

0. bed
1. sofa
2. chair
3. table
4. lamp
5. tv
6. laptop
7. wardrobe
8. window
9. door
10. potted plant
11. photo frame

## Important evaluation note

These images come from a labelled object-detection dataset. They are suitable as an initial comparison set for zero-shot models, but they must not be presented as an independent test set after training or fine-tuning a model on HomeObjects-3K.
