#!/bin/bash

PREFIX="$HOME/kernel_xiaomi_sm6225"
CLANG="clang-neutron"


#rm -rf out
mkdir -p out
#rm -rf error.log
#make O=out clean 
#make mrproper

# Build

CLANG_DIR=${PREFIX}/${CLANG}
export PATH="${CLANG_DIR}/bin:$PATH"

echo $PATH

# fog.config with bengal_perf

ARCH=arm64 scripts/kconfig/merge_config.sh -O "out" arch/arm64/configs/vendor/bengal-perf_defconfig arch/arm64/configs/vendor/xiaomi/fog.config arch/arm64/configs/vendor/xiaomi/ksu.config 

make -j $(nproc) ARCH=arm64 SUBARCH=arm64 O=out \
	CC="ccache clang"\
	AR="llvm-ar" \
	NM="llvm-nm" \
	LD="ld.lld -S" \
	OBJCOPY="llvm-objcopy" \
	OBJDUMP="llvm-objdump" \
	STRIP="llvm-strip" \
	CLANG_TRIPLE="aarch64-linux-gnu-" \
	CROSS_COMPILE="aarch64-linux-gnu-" \
	CROSS_COMPILE_ARM32="arm-linux-gnueabi-" \
	CROSS_COMPILE_COMPAT="arm-linux-gnueabi-" \
	LLVM=1 \
	LLVM_IAS=1 \
	INSTALL_MOD_STRIP=1 \
	KBUILD_BUILD_USER="$(git rev-parse --short HEAD | cut -c1-7)" \
	KBUILD_BUILD_HOST="$(git symbolic-ref --short HEAD)"	
	
ccache -s

# EOF
