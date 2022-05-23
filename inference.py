import os
from util import find_gpus
os.environ['CUDA_VISIBLE_DEVICES'] = find_gpus(nums=1) # 必须在import torch前面

import torch
from torch.utils.data import SequentialSampler, DataLoader

from config import args
from data.data_helper import MultiModalDataset
from data.category_id_map import lv2id_to_category_id, CATEGORY_ID_LIST
from models.finetune_model import ClassificationModel


def inference():
    # 1. load data
    dataset = MultiModalDataset(args, args.test_annotation, args.test_zip_feats, test_mode=True)
    sampler = SequentialSampler(dataset)
    dataloader = DataLoader(dataset,
                            batch_size=args.test_batch_size,
                            sampler=sampler,
                            drop_last=False,
                            pin_memory=True,
                            num_workers=args.num_workers)
                            #prefetch_factor=args.prefetch)

    # 2. load model
    model = ClassificationModel(len(CATEGORY_ID_LIST))
    checkpoint = torch.load(f'{args.savedmodel_path}/{args.ckpt_file}', map_location='cpu')
    model.load_state_dict(checkpoint['model_state_dict'])
    if torch.cuda.is_available():
        model = torch.nn.parallel.DataParallel(model.cuda())
    model.eval()

    # 3. inference
    predictions = []
    with torch.no_grad():
        for batch in dataloader:
            pred_label_id = model(input_ids=batch['title_input'].cuda(),
                                  attention_mask=batch['title_mask'].cuda(),
                                  visual_feats=batch['frame_input'].cuda(),
                                  visual_attention_mask=batch['frame_mask'].cuda(),
                                  inference=True)
            predictions.extend(pred_label_id.cpu().numpy())

    # 4. dump results
    with open(args.test_output_csv, 'w') as f:
        for pred_label_id, ann in zip(predictions, dataset.anns):
            video_id = ann['id']
            category_id = lv2id_to_category_id(pred_label_id)
            f.write(f'{video_id},{category_id}\n')


if __name__ == '__main__':
    inference()