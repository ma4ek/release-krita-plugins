/*
    Copyright (c) 2026 きぃ

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <https://gnu.org>.
*/
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#ifdef _WIN32
    #define DLL_EXPORT __declspec(dllexport)
#else
    #define DLL_EXPORT
#endif
DLL_EXPORT uint8_t* dispose_pPixelData(uint8_t* ptr) {
    if (ptr != NULL) {
        free(ptr);
        ptr = NULL;
    }else {
        fprintf(stderr, "Error: このポインタは使われていません。\n");
    }
    return ptr;
}
DLL_EXPORT uint8_t* setmaskData(uint8_t** maskData,uint8_t alphaval) {
    //マスクデータの透明度をそのまま投射
    **maskData = alphaval;
    return (*maskData)++;
}
DLL_EXPORT uint8_t* getNonTransparentPixelColor(uint8_t** targetPixelData,uint8_t alphaval){
    if (*targetPixelData == NULL) {
        fprintf(stderr, "targetPixelData is NULL\n");
        return NULL; // Handle null pointers
    }
    uint8_t* targetpx=(uint8_t*)&targetPixelData[0];
    uint8_t* resultColor=(uint8_t*)calloc(4,sizeof(uint8_t));
    resultColor[0] = targetpx[0];     // Blue
    resultColor[1] = targetpx[1]; // Green
    resultColor[2] = targetpx[2]; // Red
    resultColor[3] = targetpx[3]; // Alpha
    return resultColor;
}
/**
 * @brief 特定のピクセルデータを加工します。
 * 
 * 指定された座標のuint8_t型ピクセルデータを読み込み、加工処理を行います。
 *
 * @param[in] pixel_data 加工対象のピクセル配列へのポインタ
 * @param[in]     width          対象ピクセルの幅
 * @param[in]     height          対象ピクセルの高さ
 * @param[in]     callback     透明色でない色の抽出は、getNonTransparentPixelColor、
 *                             マスクデータの抽出はsetMaskDataを選んでください
 * @return        uint8_t*      getNonTransparentPixelColorのの場合、透明色でない色情報が返ります。
 *                              必要に応じてQColorなどに落とし込んでください。
 *                             setMaskDataの場合は、抽出したマスクデータが返ってきます。
 */
DLL_EXPORT uint8_t* manipulatePixelsFromPixelData(uint8_t* pixelData,uint32_t width,uint32_t height, uint8_t* (*callback)(uint8_t**,uint8_t)) {
    if (pixelData == NULL || callback == NULL) {
        if(pixelData == NULL) {
            fprintf(stderr, "Error: pixelData is NULL\n");
        }else {
            fprintf(stderr, "Error: callback is NULL\n");
        }
        return NULL; // Handle null pointers
    }
    uint8_t* maskData = NULL;//maskDataが必要ない場合はNULL
    uint8_t* maskDataPtr=NULL;//maskDataPtrはmaskDataの先頭アドレスのポインタ
    if (callback==setmaskData){
        size_t maskDataSize = width * height * sizeof(uint8_t); // Assuming RGBA format
        printf("maskDataSize=%ld\n",maskDataSize);
        maskData = (uint8_t*)calloc(maskDataSize,sizeof(uint8_t)); // Assuming RGBA format
        if (maskData == NULL) {
            fprintf(stderr, "Error: メモリの確保に失敗しました。\n");
            return NULL; // Handle memory allocation failure
        }
        maskDataPtr=&maskData[0];
    }
    for (int y = 0; y < height; ++y) {
        for (int x = 0; x < width; ++x) {
            int index = (y * width + x) * 4; // Assuming RGBA format
            uint8_t alpha = pixelData[index + 3];
            if (callback == getNonTransparentPixelColor){
                if (alpha > 0) { // Non-transparent pixel found
                        return callback((uint8_t**)&pixelData[index],0);
                    }
            }else{
                callback(&maskData,alpha);
            }
        }
    }
    return maskDataPtr;//maskDataPtrを返すことで、maskDataの先頭アドレスを返す
}