"""
project: lollms
file: lollms_extensions_infos.py 
author: ParisNeo
description: 
    This module contains a set of FastAPI routes that provide information about the Lord of Large Language and Multimodal Systems (LoLLMs) Web UI
    application. These routes are specific to handling extensions related operations.

"""
from fastapi import APIRouter, Request
from pydantic import BaseModel
import pkg_resources
from lollms.server.elf_server import LOLLMSElfServer
from lollms.extension import ExtensionBuilder, InstallOption
from lollms.utilities import gc
from ascii_colors import ASCIIColors
from lollms.utilities import load_config, trace_exception
from pathlib import Path
from typing import List
import psutil
import yaml
from lollms.security import sanitize_path, check_access

# --------------------- Parameter Classes -------------------------------
class ExtensionInstallInfos(BaseModel):
    client_id:str
    name:str
class ExtensionMountingInfos(BaseModel):
    client_id:str
    category:str
    folder:str
    language:str

# ----------------------- Defining router and main class ------------------------------

    
router = APIRouter()
lollmsElfServer = LOLLMSElfServer.get_instance()

# --------------------- Listing -------------------------------
@router.get("/list_extensions_categories")
def list_extensions_categories():
    extensions_categories_dir = lollmsElfServer.lollms_paths.extensions_zoo_path  # replace with the actual path to the models folder
    extensions_categories = [f.stem for f in extensions_categories_dir.iterdir() if f.is_dir() and not f.name.startswith(".")]
    return extensions_categories

@router.get("/list_extensions")
def list_extensions():
    return lollmsElfServer.config.extensions


@router.get("/get_all_extensions")
def get_all_extensions():
    ASCIIColors.yellow("Getting all extensions")
    extensions_folder = lollmsElfServer.lollms_paths.extensions_zoo_path
    extensions = {}

    for category_folder in  extensions_folder.iterdir():
        cat = category_folder.stem
        if category_folder.is_dir() and not category_folder.stem.startswith('.'):
            extensions[category_folder.name] = []
            for extensions_folder in category_folder.iterdir():
                ext = extensions_folder.stem
                if extensions_folder.is_dir() and not extensions_folder.stem.startswith('.'):
                    extension_info = {"folder":extensions_folder.stem}
                    config_path = extensions_folder / 'config.yaml'
                    if not config_path.exists():
                        continue                                    
                    try:
                        with open(config_path) as config_file:
                            config_data = yaml.load(config_file, Loader=yaml.FullLoader)
                            extension_info['name'] = config_data.get('name',"No Name")
                            extension_info['author'] = config_data.get('author', 'ParisNeo')
                            extension_info['based_on'] = config_data.get('based_on',"")
                            extension_info['description'] = config_data.get('description',"")
                            extension_info['version'] = config_data.get('version', '1.0.0')
                            extension_info['installed'] = (lollmsElfServer.lollms_paths.personal_configuration_path/f"personality_{extensions_folder.stem}.yaml").exists()
                            extension_info['help'] = config_data.get('help', '')

                        real_assets_path = extensions_folder/ 'assets'
                        assets_path = Path("extensions") / cat / ext / 'assets'
                        gif_logo_path = assets_path / 'logo.gif'
                        webp_logo_path = assets_path / 'logo.webp'
                        png_logo_path = assets_path / 'logo.png'
                        jpg_logo_path = assets_path / 'logo.jpg'
                        jpeg_logo_path = assets_path / 'logo.jpeg'
                        svg_logo_path = assets_path / 'logo.svg'
                        bmp_logo_path = assets_path / 'logo.bmp'

                        gif_logo_path_ = real_assets_path / 'logo.gif'
                        webp_logo_path_ = real_assets_path / 'logo.webp'
                        png_logo_path_ = real_assets_path / 'logo.png'
                        jpg_logo_path_ = real_assets_path / 'logo.jpg'
                        jpeg_logo_path_ = real_assets_path / 'logo.jpeg'
                        svg_logo_path_ = real_assets_path / 'logo.svg'
                        bmp_logo_path_ = real_assets_path / 'logo.bmp'
                            
                        extension_info['has_logo'] = png_logo_path.is_file() or gif_logo_path.is_file()
                        
                        if gif_logo_path_.exists():
                            extension_info['avatar'] = str(gif_logo_path).replace("\\","/")
                        elif webp_logo_path_.exists():
                            extension_info['avatar'] = str(webp_logo_path).replace("\\","/")
                        elif png_logo_path_.exists():
                            extension_info['avatar'] = str(png_logo_path).replace("\\","/")
                        elif jpg_logo_path_.exists():
                            extension_info['avatar'] = str(jpg_logo_path).replace("\\","/")
                        elif jpeg_logo_path_.exists():
                            extension_info['avatar'] = str(jpeg_logo_path).replace("\\","/")
                        elif svg_logo_path_.exists():
                            extension_info['avatar'] = str(svg_logo_path).replace("\\","/")
                        elif bmp_logo_path_.exists():
                            extension_info['avatar'] = str(bmp_logo_path).replace("\\","/")
                        else:
                            extension_info['avatar'] = ""
                        
                        extensions[category_folder.name].append(extension_info)
                    except Exception as ex:
                        ASCIIColors.warning(f"Couldn't load personality from {extensions_folder} [{ex}]")
                        trace_exception(ex)
    return extensions



# --------------------- Installing -------------------------------
@router.post("/install_extension")
def install_extension(data: ExtensionInstallInfos):
    check_access(lollmsElfServer, data.client_id)
    if not data.name:
        try:
            data.name=lollmsElfServer.config.extensions[-1]
        except Exception as ex:
            lollmsElfServer.error(ex)
            return
    else:
        data.name = sanitize_path(data.name)
    try:
        extension_path = lollmsElfServer.lollms_paths.extensions_zoo_path / data.name
        ASCIIColors.info(f"- Reinstalling extension {data.name}...")
        try:
            lollmsElfServer.mounted_extensions.append(ExtensionBuilder().build_extension(extension_path,lollmsElfServer.lollms_paths, lollmsElfServer, InstallOption.FORCE_INSTALL))
            return {"status":True}
        except Exception as ex:
            ASCIIColors.error(f"Extension file not found or is corrupted ({data.name}).\nReturned the following exception:{ex}\nPlease verify that the personality you have selected exists or select another personality. Some updates may lead to change in personality name or category, so check the personality selection in settings to be sure.")
            trace_exception(ex)
            ASCIIColors.info("Trying to force reinstall")
            return {"status":False, 'error':str(e)}

    except Exception as e:
        return {"status":False, 'error':str(e)}

@router.post("/reinstall_extension")
def reinstall_extension(data: ExtensionInstallInfos):
    check_access(lollmsElfServer, data.client_id)
    if not data.name:
        try:
            data.name=sanitize_path(lollmsElfServer.config.extensions[-1])
        except Exception as ex:
            lollmsElfServer.error(ex)
            return
    else:
        data.name = sanitize_path(data.name)
    try:
        extension_path = lollmsElfServer.lollms_paths.extensions_zoo_path / data.name
        ASCIIColors.info(f"- Reinstalling extension {data.name}...")
        ASCIIColors.info("Unmounting extension")
        if data.name in lollmsElfServer.config.extensions:
            idx = lollmsElfServer.config.extensions.index(data.name)
            print(f"index = {idx}")
            if len(lollmsElfServer.mount_extensions)>idx:
                del lollmsElfServer.mounted_extensions[idx]
            gc.collect()
        try:
            lollmsElfServer.mounted_extensions.append(ExtensionBuilder().build_extension(extension_path,lollmsElfServer.lollms_paths, lollmsElfServer, InstallOption.FORCE_INSTALL))
            return {"status":True}
        except Exception as ex:
            ASCIIColors.error(f"Extension file not found or is corrupted ({data.name}).\nReturned the following exception:{ex}\nPlease verify that the personality you have selected exists or select another personality. Some updates may lead to change in personality name or category, so check the personality selection in settings to be sure.")
            trace_exception(ex)
            ASCIIColors.info("Trying to force reinstall")
            return {"status":False, 'error':str(e)}

    except Exception as e:
        return {"status":False, 'error':str(e)}
    

# --------------------- Mounting -------------------------------


@router.post("/mount_extension")
def mount_extension(data:ExtensionMountingInfos):
    check_access(lollmsElfServer, data.client_id)
    print("- Mounting extension")
    category = sanitize_path(data.category)
    name = sanitize_path(data.folder)

    package_path = f"{category}/{name}"
    package_full_path = lollmsElfServer.lollms_paths.extensions_zoo_path/package_path
    config_file = package_full_path / "config.yaml"
    if config_file.exists():
        lollmsElfServer.config["extensions"].append(package_path)
        lollmsElfServer.mounted_extensions = lollmsElfServer.rebuild_extensions()
        ASCIIColors.success("ok")
        if lollmsElfServer.config.auto_save:
            ASCIIColors.info("Saving configuration")
            lollmsElfServer.config.save_config()
        ASCIIColors.success(f"Extension {name} mounted successfully")
        return {"status": True,
                        "extensions":lollmsElfServer.config["extensions"],
                        }       
    else:
        pth = str(config_file).replace('\\','/')
        ASCIIColors.error(f"nok : Extension not found @ {pth}")
        return {"status": False, "error":f"Extension not found @ {pth}"}


@router.post("/remount_extension")
def remount_extension(data:ExtensionMountingInfos):
    check_access(lollmsElfServer, data.client_id)
    print("- Remounting extension")
    category = sanitize_path(data.category)
    name = sanitize_path(data.folder)

    package_path = f"{category}/{name}"
    package_full_path = lollmsElfServer.lollms_paths.extensions_zoo_path/package_path
    config_file = package_full_path / "config.yaml"
    if config_file.exists():
        ASCIIColors.info(f"Unmounting personality {package_path}")
        index = lollmsElfServer.config["extensions"].index(f"{category}/{name}")
        lollmsElfServer.config["extensions"].remove(f"{category}/{name}")
        if len(lollmsElfServer.config["extensions"])>0:
            lollmsElfServer.mounted_personalities = lollmsElfServer.rebuild_extensions()
        else:
            lollmsElfServer.personalities = ["generic/lollms"]
            lollmsElfServer.mounted_personalities = lollmsElfServer.rebuild_extensions()


        ASCIIColors.info(f"Mounting personality {package_path}")
        lollmsElfServer.config["personalities"].append(package_path)
        lollmsElfServer.mounted_personalities = lollmsElfServer.rebuild_extensions()
        ASCIIColors.success("ok")
        if lollmsElfServer.config["active_personality_id"]<0:
            return {"status": False,
                            "personalities":lollmsElfServer.config["personalities"],
                            "active_personality_id":lollmsElfServer.config["active_personality_id"]
                            }     
        else:
            return {"status": True,
                            "personalities":lollmsElfServer.config["personalities"],
                            "active_personality_id":lollmsElfServer.config["active_personality_id"]
                            }
    else:
        pth = str(config_file).replace('\\','/')
        ASCIIColors.error(f"nok : Personality not found @ {pth}")
        ASCIIColors.yellow(f"Available personalities: {[p.name for p in lollmsElfServer.mounted_personalities]}")
        return {"status": False, "error":f"Personality not found @ {pth}"} 

@router.post("/unmount_extension")
def unmount_extension(data:ExtensionMountingInfos):
    check_access(lollmsElfServer, data.client_id)
    print("- Unmounting extension ...")
    category    = sanitize_path(data.category)
    name        = sanitize_path(data.folder)
    language    = sanitize_path(data.get('language',None))
    try:
        personality_id = f"{category}/{name}" if language is None else f"{category}/{name}:{language}"
        index = lollmsElfServer.config["personalities"].index(personality_id)
        lollmsElfServer.config["extensions"].remove(personality_id)
        lollmsElfServer.mounted_extensions = lollmsElfServer.rebuild_extensions()
        ASCIIColors.success("ok")
        if lollmsElfServer.config.auto_save:
            ASCIIColors.info("Saving configuration")
            lollmsElfServer.config.save_config()
        return {
                    "status": True,
                    "extensions":lollmsElfServer.config["extensions"]
                    }        
    except:
        if language:
            ASCIIColors.error(f"nok : Personality not found @ {category}/{name}:{language}")
        else:
            ASCIIColors.error(f"nok : Personality not found @ {category}/{name}")
            
        ASCIIColors.yellow(f"Available personalities: {[p.name for p in lollmsElfServer.mounted_personalities]}")
        return {"status": False, "error":"Couldn't unmount personality"}
