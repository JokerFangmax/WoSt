# 3. Clean and Build
rm -rf build
mkdir build && cd build
cmake ..
make -j$(nproc)

cd ..

build/wost
