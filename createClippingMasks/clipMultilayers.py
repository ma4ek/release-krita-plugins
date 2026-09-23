# -*- coding: utf-8 -*-
"""
Copyright (c) 2026 きぃ(ma4ek)

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
"""

from krita import *
from krita import Extension, Krita,QColor
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import *
from pathlib import Path
import locale
import ctypes,os,platform,time
import gc
from contextlib import contextmanager
class clipMultilayers(Extension):
    def __init__(self, parent):
        super().__init__(parent)
    def setup(self):
        # Kritaの起動時に呼ばれるセットアップ処理
        libdir=os.path.dirname(__file__)
        current_os=platform.system()
        lib_name=None
        if current_os=="Windows":
            lib_name="colorconv.dll"
        elif current_os=="Darwin":
            lib_name="colorconv.dylib"
        else:
            lib_name="colorconv.so"
        lib_path=os.path.join(libdir,"libs",lib_name)
        self.clrconvLib=ctypes.CDLL(lib_path)
    def my_i18n(self,msg_id):
        translations = {
            "pluginTitle":{
                "ja": "クリッピングマスク一括生成",
                "en": "Generate Clipping Masks by each layer"
            },
            "colorNotFound_msg": {
                "ja": "色が見つかりませんでした。",
                "en": "Color not found."
            },
            "docNotFound_msg": {
                "ja": "ドキュメントが開いていません。",
                "en": "Document is not open."
            },
            "layerNotFound_msg": {
                "ja": "レイヤーが選択してください。",
                "en": "Choose layers."
            },
            "InProgress_msg":{
                "ja": "進行中",
                "en": "InProgress"
            },
            "Done_msg":{
                "ja": "完了",
                "en": "Done."
            }
            # 必要に応じてここにどんどん追加できます
        }
        # 登録したIDが見つからない場合は、IDをそのまま返す（安全対策）
        if msg_id not in translations:
            print(f"Your messsage id is not found.:{msg_id}")
            return msg_id
        # Kritaが日本語設定なら日本語、それ以外なら英語を返す
        return translations[msg_id]["ja" if self.current_lang else "en"]
    def createActions(self, window):
        # メニューにアクション（ボタン）を追加
        self.application = Krita.instance()
        try:
            def_locale=locale.getlocale().lower()
        except Exception:
            def_locale="en"
        self.current_lang=def_locale[:2]
        self.plugin_Title=self.my_i18n("pluginTitle")
        action = window.createAction("clipMultiLayers_action", "クリッピングマスク一括生成", "tools/scripts")
        action.triggered.connect(self.run_process)
        '''
            manipulatePixelsFromPixelData関数の定義部分
        '''
        self.callback=ctypes.CFUNCTYPE(
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.POINTER(ctypes.POINTER(ctypes.c_uint8)),
            ctypes.c_uint8
        )
        self.clrconvLib.manipulatePixelsFromPixelData.restype=ctypes.POINTER(ctypes.c_uint8)
        self.clrconvLib.manipulatePixelsFromPixelData.argtypes=[
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.c_uint32,
            ctypes.c_uint32,
            self.callback
        ]
        '''
            コールバック関数：getNonTransparentPixelColorの定義。
        '''
        self.clrconvLib.getNonTransparentPixelColor.restype=ctypes.POINTER(ctypes.c_uint8)
        self.clrconvLib.getNonTransparentPixelColor.argtypes=[
            ctypes.POINTER(ctypes.POINTER(ctypes.c_uint8)),
            ctypes.c_uint8
        ]
        '''
            コールバック関数：setmaskDataの定義。
        '''
        self.clrconvLib.setmaskData.restype=ctypes.POINTER(ctypes.c_uint8)
        self.clrconvLib.setmaskData.argtypes=[
            ctypes.POINTER(ctypes.POINTER(ctypes.c_uint8)),
            ctypes.c_uint8
        ]
        '''
            メモリ解放関数：dispose_pPixelDataの定義。
        '''
        self.clrconvLib.dispose_pPixelData.restype=ctypes.c_uint8
        self.clrconvLib.dispose_pPixelData.argtypes=[
            ctypes.POINTER(ctypes.c_uint8)
        ]
        self.manipulatePixelsFromPixelData=self.clrconvLib.manipulatePixelsFromPixelData 
    def run_process(self):
        @contextmanager
        def manipulatePixelsFromPixelData(pixel_data,width,height,callback):
            """ピクセル配列の色変換を行う関数です。

                C言語(colorconv.dylib)の高速ロジックを直接呼び出します。with文を併用しないとエラーになります！！

                Args:
                    pixel_data(ctypes.POINTER(ctypes.c_uint8)):加工対象のピクセルデータ。
                    width(c_uint32):ピクセルの幅。
                    height(c_uint32):ピクセルの高さ。
                    callback(ctypes.CFUNCTYPE):getNonTransparentPixelColor関数場合、透明色でない色情報が返ります。
                        必要に応じてQColorなどに落とし込んでください。
                        setmaskDataの場合は、抽出したマスクデータが返ってきます。
                
                Returns:
                    None
            """
            try:
                mask_dataptr=yield self.manipulatePixelsFromPixelData(pixel_data,width,height,callback)
            finally:
                print('動的メモリを解放します。')
                return self.clrconvLib.dispose_pPixelData(mask_dataptr)
        def calculate_area(node):
            """
                色の面積（バウンディングボックスの面積）を概算する
            """
            bounds = node.bounds() # QRect型が返る (x, y, width, height)
            width = bounds.width()
            height = bounds.height()
            return width * height
        def get_target_layers(nodes):
            """
                a. グループの場合は中身、b. 単体レイヤーの場合はそれ自身をリストで返す
            """
            ret_layers = []
            for node in nodes:
                if node.type() == "grouplayer":
                    ret_layers.extend(node.childNodes())
                else:
                    ret_layers.append(node)
            return ret_layers
        def create_fill_layer_with_mask(doc,target_layer):
            """
                塗りつぶしレイヤーにマスクをかける
            """
            if not target_layer:
                msg_text=self.my_i18n("layerNotFound_msg")
                print(msg_text)
                return
            pixel_data = target_layer.pixelData(0, 0, doc.width(), doc.height())
            found_color = None
            getNonTransparentPixelColor,setmaskData=[
                ctypes.cast(self.clrconvLib.getNonTransparentPixelColor,self.callback),\
                ctypes.cast(self.clrconvLib.setmaskData,self.callback)\
            ]
            pPixel_data=(ctypes.c_uint8*len(pixel_data)).from_buffer(pixel_data)
            with manipulatePixelsFromPixelData(pPixel_data,doc.width(),doc.height(),getNonTransparentPixelColor) as firstColor:
                b,g,r,a=ctypes.string_at(firstColor,4)
            found_color=QColor(r,g,b,a)
            if not found_color:
                msg_text=self.my_i18n("colorNotFound_msg")
                msg=QMessageBox()
                msg.setIcon(QMessageBox.Warning)
                msg.setText(msg_text)
                msg.setWindowTitle(self.plugin_Title)
                msg.setDetailedText(f"found_color={found_color}")
                msg.setStandardButtons(QMessageBox.Ok)
                msg.exec_()
                return

            fill_info = InfoObject()
            fill_info.setProperty("color", found_color)
            sel_allCanvas=Selection()
            sel_allCanvas.select(0,0,doc.width(),doc.height(),255) 
            fill_layer = doc.createFillLayer("c", "color", fill_info,sel_allCanvas)
            mask_node = doc.createTransparencyMask("mask_c")
            with manipulatePixelsFromPixelData(pPixel_data,doc.width(),doc.height(),setmaskData) as pmask_data:
                mask_data=ctypes.string_at(pmask_data,doc.width()*doc.height())
                mask_node.setPixelData(bytes(mask_data), 0, 0, doc.width(), doc.height())
            fill_layer.addChildNode(mask_node, None)
            # 2 & 3. 元のレイヤー「c」の処理（白塗りつぶし・切り取りの代替として削除）
            # 用途がマスクへの転写であるため、元の「c」レイヤーを削除して完全に置き換えます
            target_layer.remove()
            pixel_data.clear()
            return fill_layer

        def process_layer_clipping(target_layer, doc):
            """
                各色レイヤーに対してクリッピングマスク構造を作成する
            """
            original_name = target_layer.name()
            parent = target_layer.parentNode()
            group_name = original_name
            target_layer.setName("c")
            if parent is not None and target_layer is not None:
                parent.removeChildNode(target_layer)
            else:
                return
            if target_layer.type() == "paintlayer":
                target_layer=create_fill_layer_with_mask(doc,target_layer)
            new_group = doc.createGroupLayer(group_name)
            new_group.addChildNode(target_layer,None)
            s_layer = doc.createNode("s", "paintlayer")
            s_layer.setInheritAlpha(True)
            print(f"処理完了: {original_name} -> グループ化 [s (クリッピング) / c]")
            new_group.addChildNode(s_layer,target_layer)
            parent.addChildNode(new_group,None)

        view=self.application.activeWindow().activeView()
        if view:
            selected_nodes=view.selectedNodes()
        doc = self.application.activeDocument()
        if not doc:
            msg_text=self.my_i18n("docNotFound_msg")
            msg=QMessageBox()
            msg.setIcon(QMessageBox.Warning)
            msg.setText(msg_text)
            msg.setWindowTitle(self.plugin_Title)
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec_()
            return
        paint_layers=[get_target_layer for get_target_layer in get_target_layers(selected_nodes) if get_target_layer.type()!="grouplayer"] 
        seen=set()
        paint_layers=[paint_layer for paint_layer in paint_layers if id(paint_layer) not in seen and not seen.add(id(paint_layer))]
        paint_layers.sort(key=calculate_area,reverse=True)
        if not paint_layers:
            #ダイアログメッセージを表示
            msg_text=self.my_i18n("layerNotFound_msg")
            print(msg_text)
            return
        doc.waitForDone()
        layers_num=len(paint_layers) 
        for i,lay in enumerate(paint_layers):
            begin_time=time.time()
            process_layer_clipping(lay, doc)
            prograte=(i+1)/layers_num
            end_time=time.time()
            elapsed_time=end_time-begin_time
            estimated_time=elapsed_time*(layers_num-(i+1))
            msg_text=f"{self.my_i18n("InProgress_msg")}: {prograte:.0%} - {i+1}/{layers_num} estimated Time: {estimated_time:.0f}s"
            view.showFloatingMessage(msg_text,self.application.icon("selection-info"),2000,1)
        msg_text=self.my_i18n("Done_msg")
        view.showFloatingMessage(msg_text,self.application.icon("selection-info"),2000,1)
        del paint_layers
        gc.collect()