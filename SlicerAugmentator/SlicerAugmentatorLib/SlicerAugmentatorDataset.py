import slicer
from SlicerAugmentatorLib.SlicerAugmentatorUtils import sanitizeTransformName, extract_device_number
import SimpleITK as sitk
import re
try:
    import torch
    from torch.utils.data import Dataset
    from monai.transforms import RandomizableTransform
except ModuleNotFoundError:
    slicer.util.pip_install("monai[itk]")
    import torch
    from torch.utils.data import Dataset
    from monai.transforms import RandomizableTransform

class SlicerAugmentatorDataset(Dataset):
    def __init__(self, imgPaths, maskPaths=None, transformations=[], device: str="CPU"):
        self.imgPaths = imgPaths
        self.maskPaths = maskPaths
        self.transformations = transformations
        self.device = extract_device_number(device) if device != "CPU" else "cpu"

    def __len__(self):
        return len(self.imgPaths)

    def load(self, path: str) -> torch.Tensor:
        try:
            if (path):
                img = sitk.ReadImage(path)
                img_array = sitk.GetArrayFromImage(img)
                data = torch.tensor(img_array)
                return data
            return None
        except:
            return None
        
    def apply_transform(self, transform, img, transformedList: list) -> list:
        try:
            transform_name = transform.get_transform_info()["class"]
        except AttributeError:
            # in this case get_transform_info is missing, so recover the name starting from __class__:
            transform_name = sanitizeTransformName(transform)

        transformedImg = transform(img.float())
        # adding ["rotate", torch.Tensor[[...]] ]
        transformedList.append([transform_name, transformedImg])
        
        return transformedList
    
    def apply_dict_transform(self, transform, data_dict, transformedImages: list, transformedMasks: list = None) -> list:
        try:
            transform_name = transform.get_transform_info()["class"]
        except AttributeError:
            # in this case get_transform_info is missing, so recover the name starting from __class__:
            transform_name = sanitizeTransformName(transform)
        
        
        if(transformedMasks != None):
            transformedImg, transformedMask = transform(data_dict).values()
            # adding ["rotate", torch.Tensor[[...]] ]
            transformedImages.append([transform_name, transformedImg])
            transformedMasks.append([transform_name, transformedMask])
            return transformedImages, transformedMasks
        
        transformedImg = transform(data_dict)
        transformedImages.append([transform_name, transformedImg["img"]])
        return transformedImages, []

    def __getitem__(self, idx) -> tuple[list[list[str, torch.Tensor]], list[list[str, torch.Tensor]]]:
        """
        Returns:
            transformedImgs | transformedMasks  =  [
                ["rotate", torch.Tensor[[...]] ],
                ["rotate", torch.Tensor[[...]] ],
                ["flip", torch.Tensor[[...]] ],
                ["flip", torch.Tensor[[...]] ],
                ...
            ]
        """
        transformedImages = []
        transformedMasks = []
        mask = None
        
        img = self.load(self.imgPaths[idx])
        if self.maskPaths is not None and len(self.maskPaths) > 0:
            mask = self.load(self.maskPaths[idx])

        for transform in self.transformations:
            if (img != None and mask != None and isinstance(transform, RandomizableTransform)): 
                transformedImages, transformedMasks = self.apply_dict_transform(transform, {"img": img.to(self.device), "mask": mask.to(self.device)}, transformedImages, transformedMasks)
            
            if (img != None and mask == None and isinstance(transform, RandomizableTransform)): 
                transformedImages, transformedMasks = self.apply_dict_transform(transform, {"img": img.to(self.device)}, transformedImages, None)

            if (img != None and not isinstance(transform, RandomizableTransform)): 
                transformedImages = self.apply_transform(transform, img.to(self.device), transformedImages)
           
            if (mask != None and not isinstance(transform, RandomizableTransform)): 
                transformedMasks = self.apply_transform(transform, mask.to(self.device), transformedMasks)
            
        return transformedImages, transformedMasks
