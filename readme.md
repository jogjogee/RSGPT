# RSGPT: A Generative Transformer Foundation Model Pre-trained on Ten Billion Data for Retrosynthesis Planning


Available retrosynthesis data are limited to only millions. Therefore, we pioneering utilized the RDChiral reverse synthesis template extraction algorithm to generate chemical reaction data. This method precisely aligns an existing template’s reaction center with those of synthons, yielding a complete reaction. Consequently, **over 10 billion high-quality** reaction data entries were generated. A generative pretrained transformer (GPT) foundation model called RSGPT was subsequently developed for template-free retrosynthesis planning, by pre-training using the 10 billion generated reaction data. Inspired by the strategies of LLMs, we introduced reinforcement learning from AI feedback to capture the relationships among products, reactants, and templates more accurately. Extensive experiments demonstrate that our model achieves state-of-the-art performance on the USPTO-50K dataset, with a Top-1 accuracy of **63.4%**, substantially outperforming previous models. To the best of our knowledge, RSGPT is the pioneering GPT foundation model for retrosynthesis planning, providing groundbreaking insights and potential scalability across a wide range of chemical scenarios and applications.
## Table of Contents

- [Installation](#installation)
- [Usage](#usage)

## Installation

Instructions on how to install and set up the project.

```bash
# Clone the repository
git clone https://github.com/Zhao-Xinda/RSGPT.git

# Navigate to the project directory
cd yourproject

# Install dependencies
conda env create -f environment.yml
```

## Usage

**For Custom Data**
```
# Modify the input and model paths in the code file
python test_case.py

cases = [
"N#CC1=C(OCC(C)C)C=CC(C2=NC(C)=C(C(O)=O)S2)=C1"
]
```

**For Uspto Data**
```
python test.py

write2txt(\
    data_name = '50k',\ # 50k or full or mit
    pt_path = 'finetune_50k_label/ train_epoch_2.pth',\  # model path folder
    label=True,         # data with reaction label
    test_aug=False      # data with augmentation
    )
```