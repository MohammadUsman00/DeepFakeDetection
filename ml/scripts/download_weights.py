import os
import torch
from torchvision.models import efficientnet_b0, EfficientNet_B0_Weights
from pathlib import Path

def main():
    # Target path as expected by backend config
    target_dir = Path("data/models")
    target_path = target_dir / "efficientnet_b0.pth"

    print(f"Ensuring directory exists: {target_dir}")
    target_dir.mkdir(parents=True, exist_ok=True)

    print("Initializing EfficientNet-B0 with ImageNet weights...")
    # We download the official ImageNet weights as a high-quality backbone.
    # In a production deepfake system, this would be replaced by a 
    # checkpoint fine-tuned on FaceForensics++ or similar.
    model = efficientnet_b0(weights=EfficientNet_B0_Weights.DEFAULT)
    
    # The backend expects a binary classifier head (2 outputs)
    in_features = model.classifier[1].in_features
    model.classifier[1] = torch.nn.Linear(in_features, 2)

    print(f"Saving model weights to {target_path}...")
    torch.save(model.state_dict(), target_path)
    
    print("\nSUCCESS: Model weights populated.")
    print(f"Location: {target_path.absolute()}")
    print("The backend will now recognize these weights on the next startup.")

if __name__ == "__main__":
    main()
