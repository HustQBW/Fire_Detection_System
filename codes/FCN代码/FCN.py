
import numpy as np
import torch
from torchvision import models
from torch import nn
from torch.utils.tensorboard import SummaryWriter


def bilinear_kernel(in_channels, out_channels, kernel_size):
    """Define a bilinear kernel according to in channels and out channels.
    Returns:
        return a bilinear filter tensor
    """
    factor = (kernel_size + 1) // 2
    if kernel_size % 2 == 1:
        center = factor - 1
    else:
        center = factor - 0.5
    og = np.ogrid[:kernel_size, :kernel_size]
    bilinear_filter = (1 - abs(og[0] - center) / factor) * (1 - abs(og[1] - center) / factor)
    weight = np.zeros((in_channels, out_channels, kernel_size, kernel_size), dtype=np.float32)
    weight[range(in_channels), range(out_channels), :, :] = bilinear_filter
    return torch.from_numpy(weight)


pretrained_net = models.vgg16_bn(pretrained=True)
# print(pretrained_net.features)# pretrained_net.features[0]代表第0层


class FCN(nn.Module):
    def __init__(self, num_classes):
        super().__init__()

        self.stage1 = pretrained_net.features[:7]#第一个上采样块
        self.stage2 = pretrained_net.features[7:14]#第二个上采样块
        self.stage3 = pretrained_net.features[14:24]#第三个上采样块
        self.stage4 = pretrained_net.features[24:34]#第四个上采样块
        self.stage5 = pretrained_net.features[34:]#第五个上采样块

        self.scores1 = nn.Conv2d(512, num_classes, 1)#1x1卷积核
        self.scores2 = nn.Conv2d(512, num_classes, 1)#1x1卷积核
        self.scores3 = nn.Conv2d(128, num_classes, 1)#1x1卷积核

        self.conv_trans1 = nn.Conv2d(512, 256, 1)
        self.conv_trans2 = nn.Conv2d(256, num_classes, 1)

        self.upsample_8x = nn.ConvTranspose2d(num_classes, num_classes, 16, 8, 4, bias=False)
        self.upsample_8x.weight.data = bilinear_kernel(num_classes, num_classes, 16)

        self.upsample_2x_1 = nn.ConvTranspose2d(512, 512, 4, 2, 1, bias=False)
        self.upsample_2x_1.weight.data = bilinear_kernel(512, 512, 4)

        self.upsample_2x_2 = nn.ConvTranspose2d(256, 256, 4, 2, 1, bias=False)
        self.upsample_2x_2.weight.data = bilinear_kernel(256, 256, 4)

    def forward(self, x):   # 352, 480, 3
        s1 = self.stage1(x)     # 176, 240, 64
        s2 = self.stage2(s1)    # 88, 120, 128
        s3 = self.stage3(s2)    # 44, 60, 256
        s4 = self.stage4(s3)    # 22, 30, 512
        s5 = self.stage5(s4)    # 11, 15, 512

        scores1 = self.scores1(s5)  # 11, 15, 12
        s5 = self.upsample_2x_1(s5) # 22, 30, 512
        add1 = s4 + s5  # 22, 30, 512

        scores2 = self.scores2(add1)    # 22, 30, 12
        add1 = self.conv_trans1(add1)   # 22, 30, 256
        add1 = self.upsample_2x_2(add1) # 44, 60, 256

        add2 = add1 + s3    # 44, 60, 256

        add2 = self.conv_trans2(add2)   # 44，60，12
        scores3 = self.upsample_8x(add2)    # 352, 480, 12

        return scores3




if __name__ == "__main__":
    import torch as t
    print('-----'*5)
    rgb = t.randn(1, 3, 480,640)

    net = FCN(2)
    # print(net)
    with SummaryWriter(log_dir='net_structure',comment='Net_FCN') as w:
        w.add_graph(net,(rgb,))
    out = net(rgb)

    print(out.shape)