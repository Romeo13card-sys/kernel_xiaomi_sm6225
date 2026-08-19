#CONFIGURATION
defconfig_path=arch/arm64/configs/vendor/fog_defconfig # Must be edited
defconfig=vendor/fog_defconfig # Must be edited

#Resukisu
curl -LSs "https://raw.githubusercontent.com/ReSukiSU/ReSukiSU/main/kernel/setup.sh" | bash

#KSU ACTIVATION
echo "CONFIG_KSU=y" >> $defconfig_path

#MANUAL HOOK
echo "CONFIG_KSU_MANUAL_HOOK=y" >> $defconfig_path
wget https://raw.githubusercontent.com/xxblebleblexx/manual_hook_fix/refs/heads/main/resuki-4.19-cip-st.patch;wait;patch -p1 < resuki-4.19-cip-st.patch

#SUSFS v2.2
echo "CONFIG_KSU_SUSFS=y" >> $defconfig_path
echo "CONFIG_KSU_SUSFS_SUS_PATH=y" >> $defconfig_path
echo "CONFIG_KSU_SUSFS_SUS_MOUNT=y" >> $defconfig_path
echo "CONFIG_KSU_SUSFS_SUS_KSTAT=y" >> $defconfig_path
echo "CONFIG_KSU_SUSFS_TRY_UMOUNT=n" >> $defconfig_path
echo "CONFIG_KSU_SUSFS_SPOOF_UNAME=y" >> $defconfig_path
echo "CONFIG_KSU_SUSFS_ENABLE_LOG=n" >> $defconfig_path
echo "CONFIG_KSU_SUSFS_HIDE_KSU_SUSFS_SYMBOLS=y" >> $defconfig_path
echo "CONFIG_KSU_SUSFS_SPOOF_CMDLINE_OR_BOOTCONFIG=y" >> $defconfig_path
echo "CONFIG_KSU_SUSFS_OPEN_REDIRECT=y" >> $defconfig_path
echo "CONFIG_KSU_SUSFS_SUS_MAP=y" >> $defconfig_path
wget https://github.com/xxblebleblexx/android_kernel_xiaomi_sm6225/commit/82a531eefef0f5a5915eba08b143aa76e61e4fa4.diff;patch -p1 < 82a531eefef0f5a5915eba08b143aa76e61e4fa4.diff


#Nomount driver
curl -LSs "https://raw.githubusercontent.com/xxblebleblexx/nomount-installer/refs/heads/installer/nomount.sh" | bash -s 4.19

make O=out ARCH=arm64 $defconfig; printf "n\n2\n\n\n\nY\n" | make -j$(nproc --all) CC=clang O=out ARCH=arm64 LLVM=1 LLVM_IAS=1 LD=ld.lld AS=llvm-as AR=llvm-ar NM=llvm-nm OBJCOPY=llvm-objcopy OBJDUMP=llvm-objdump READELF=llvm-readelf STRIP=llvm-strip
