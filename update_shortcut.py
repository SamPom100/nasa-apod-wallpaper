#!/usr/bin/env python3
"""
Update APOD_Wallpaper shortcut to skip videos and pick a random past APOD.
"""

import os
import plistlib
import sqlite3
import subprocess
import uuid

def gen_uuid():
    return str(uuid.uuid4()).upper()

def build_workflow():
    u_today_url = gen_uuid()
    u_today_item = gen_uuid()
    u_today_content = gen_uuid()
    u_today_rendered = gen_uuid()
    u_today_match = gen_uuid()
    group_is_video = gen_uuid()

    u_rand_num = gen_uuid()
    u_rand_url = gen_uuid()
    u_rand_item = gen_uuid()
    u_rand_content = gen_uuid()
    u_rand_rendered = gen_uuid()
    u_rand_match = gen_uuid()
    group_rand_is_video = gen_uuid()

    u_fb_url = gen_uuid()
    u_fb_item = gen_uuid()
    u_fb_feat = gen_uuid()
    u_fb_file = gen_uuid()
    u_fb_setvar = gen_uuid()

    u_rand_feat = gen_uuid()
    u_rand_file = gen_uuid()
    u_rand_setvar = gen_uuid()
    u_rand_endif = gen_uuid()

    u_today_feat = gen_uuid()
    u_today_file = gen_uuid()
    u_today_setvar = gen_uuid()
    u_today_endif = gen_uuid()

    u_replace = gen_uuid()
    u_img_url = gen_uuid()
    u_detect = gen_uuid()
    group_img_valid = gen_uuid()

    u_notif = gen_uuid()
    u_resize = gen_uuid()
    u_set_wall = gen_uuid()
    u_valid_endif = gen_uuid()

    prefix = "https://science.nasa.gov/wp-json/wp/v2/image-article?categories=22766&per_page=1&page="

    actions = [
        # 0. Download today's APOD metadata
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.downloadurl",
            "WFWorkflowActionParameters": {
                "WFURL": "https://science.nasa.gov/wp-json/wp/v2/image-article?categories=22766&per_page=1",
                "UUID": u_today_url
            }
        },
        # 1. Get first item
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.getitemfromlist",
            "WFWorkflowActionParameters": {
                "WFInput": {
                    "Value": {
                        "OutputUUID": u_today_url,
                        "Type": "ActionOutput",
                        "OutputName": "Contents of URL"
                    },
                    "WFSerializationType": "WFTextTokenAttachment"
                },
                "WFItemSpecifier": "First Item",
                "UUID": u_today_item
            }
        },
        # 2. Get content dictionary
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.getvalueforkey",
            "WFWorkflowActionParameters": {
                "WFInput": {
                    "Value": {
                        "OutputUUID": u_today_item,
                        "Type": "ActionOutput",
                        "OutputName": "Item from List"
                    },
                    "WFSerializationType": "WFTextTokenAttachment"
                },
                "WFGetDictionaryValueType": "Value",
                "WFDictionaryKey": {
                    "Value": {
                        "string": "content",
                        "attachmentsByRange": {}
                    },
                    "WFSerializationType": "WFTextTokenString"
                },
                "UUID": u_today_content
            }
        },
        # 3. Get rendered HTML string
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.getvalueforkey",
            "WFWorkflowActionParameters": {
                "WFInput": {
                    "Value": {
                        "OutputUUID": u_today_content,
                        "Type": "ActionOutput",
                        "OutputName": "Dictionary Value"
                    },
                    "WFSerializationType": "WFTextTokenAttachment"
                },
                "WFGetDictionaryValueType": "Value",
                "WFDictionaryKey": {
                    "Value": {
                        "string": "rendered",
                        "attachmentsByRange": {}
                    },
                    "WFSerializationType": "WFTextTokenString"
                },
                "UUID": u_today_rendered
            }
        },
        # 4. Match video/iframe tags
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.text.match",
            "WFWorkflowActionParameters": {
                "text": {
                    "Value": {
                        "string": "\ufffc",
                        "attachmentsByRange": {
                            "{0, 1}": {
                                "OutputUUID": u_today_rendered,
                                "Type": "ActionOutput",
                                "OutputName": "Dictionary Value"
                            }
                        }
                    },
                    "WFSerializationType": "WFTextTokenString"
                },
                "WFMatchTextPattern": "(?i)<(video|iframe)",
                "WFMatchTextCaseSensitive": False,
                "UUID": u_today_match
            }
        },
        # 5. If today is a video
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.conditional",
            "WFWorkflowActionParameters": {
                "WFInput": {
                    "Type": "Variable",
                    "Variable": {
                        "Value": {
                            "OutputUUID": u_today_match,
                            "Type": "ActionOutput",
                            "OutputName": "Matches"
                        },
                        "WFSerializationType": "WFTextTokenAttachment"
                    }
                },
                "WFControlFlowMode": 0,
                "GroupingIdentifier": group_is_video,
                "WFCondition": 100
            }
        },
        # 6. Generate random number between 3 and 365
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.number.random",
            "WFWorkflowActionParameters": {
                "WFRandomNumberMinimum": "3",
                "WFRandomNumberMaximum": "365",
                "UUID": u_rand_num
            }
        },
        # 7. Download random past APOD
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.downloadurl",
            "WFWorkflowActionParameters": {
                "WFURL": {
                    "Value": {
                        "string": f"{prefix}\ufffc",
                        "attachmentsByRange": {
                            f"{{{len(prefix)}, 1}}": {
                                "OutputUUID": u_rand_num,
                                "Type": "ActionOutput",
                                "OutputName": "Random Number"
                            }
                        }
                    },
                    "WFSerializationType": "WFTextTokenString"
                },
                "UUID": u_rand_url
            }
        },
        # 8. First item of random page
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.getitemfromlist",
            "WFWorkflowActionParameters": {
                "WFInput": {
                    "Value": {
                        "OutputUUID": u_rand_url,
                        "Type": "ActionOutput",
                        "OutputName": "Contents of URL"
                    },
                    "WFSerializationType": "WFTextTokenAttachment"
                },
                "WFItemSpecifier": "First Item",
                "UUID": u_rand_item
            }
        },
        # 9. Get content of random item
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.getvalueforkey",
            "WFWorkflowActionParameters": {
                "WFInput": {
                    "Value": {
                        "OutputUUID": u_rand_item,
                        "Type": "ActionOutput",
                        "OutputName": "Item from List"
                    },
                    "WFSerializationType": "WFTextTokenAttachment"
                },
                "WFGetDictionaryValueType": "Value",
                "WFDictionaryKey": {
                    "Value": {
                        "string": "content",
                        "attachmentsByRange": {}
                    },
                    "WFSerializationType": "WFTextTokenString"
                },
                "UUID": u_rand_content
            }
        },
        # 10. Get rendered HTML of random item
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.getvalueforkey",
            "WFWorkflowActionParameters": {
                "WFInput": {
                    "Value": {
                        "OutputUUID": u_rand_content,
                        "Type": "ActionOutput",
                        "OutputName": "Dictionary Value"
                    },
                    "WFSerializationType": "WFTextTokenAttachment"
                },
                "WFGetDictionaryValueType": "Value",
                "WFDictionaryKey": {
                    "Value": {
                        "string": "rendered",
                        "attachmentsByRange": {}
                    },
                    "WFSerializationType": "WFTextTokenString"
                },
                "UUID": u_rand_rendered
            }
        },
        # 11. Match video tags on random item
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.text.match",
            "WFWorkflowActionParameters": {
                "text": {
                    "Value": {
                        "string": "\ufffc",
                        "attachmentsByRange": {
                            "{0, 1}": {
                                "OutputUUID": u_rand_rendered,
                                "Type": "ActionOutput",
                                "OutputName": "Dictionary Value"
                            }
                        }
                    },
                    "WFSerializationType": "WFTextTokenString"
                },
                "WFMatchTextPattern": "(?i)<(video|iframe)",
                "WFMatchTextCaseSensitive": False,
                "UUID": u_rand_match
            }
        },
        # 12. If random item is also a video
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.conditional",
            "WFWorkflowActionParameters": {
                "WFInput": {
                    "Type": "Variable",
                    "Variable": {
                        "Value": {
                            "OutputUUID": u_rand_match,
                            "Type": "ActionOutput",
                            "OutputName": "Matches"
                        },
                        "WFSerializationType": "WFTextTokenAttachment"
                    }
                },
                "WFControlFlowMode": 0,
                "GroupingIdentifier": group_rand_is_video,
                "WFCondition": 100
            }
        },
        # 13. Fallback: Download page 2 (yesterday, guaranteed image)
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.downloadurl",
            "WFWorkflowActionParameters": {
                "WFURL": "https://science.nasa.gov/wp-json/wp/v2/image-article?categories=22766&per_page=1&page=2",
                "UUID": u_fb_url
            }
        },
        # 14. First item of fallback
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.getitemfromlist",
            "WFWorkflowActionParameters": {
                "WFInput": {
                    "Value": {
                        "OutputUUID": u_fb_url,
                        "Type": "ActionOutput",
                        "OutputName": "Contents of URL"
                    },
                    "WFSerializationType": "WFTextTokenAttachment"
                },
                "WFItemSpecifier": "First Item",
                "UUID": u_fb_item
            }
        },
        # 15. Get featured_image from fallback
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.getvalueforkey",
            "WFWorkflowActionParameters": {
                "WFInput": {
                    "Value": {
                        "OutputUUID": u_fb_item,
                        "Type": "ActionOutput",
                        "OutputName": "Item from List"
                    },
                    "WFSerializationType": "WFTextTokenAttachment"
                },
                "WFGetDictionaryValueType": "Value",
                "WFDictionaryKey": {
                    "Value": {
                        "string": "featured_image",
                        "attachmentsByRange": {}
                    },
                    "WFSerializationType": "WFTextTokenString"
                },
                "UUID": u_fb_feat
            }
        },
        # 16. Get file from fallback
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.getvalueforkey",
            "WFWorkflowActionParameters": {
                "WFInput": {
                    "Value": {
                        "OutputUUID": u_fb_feat,
                        "Type": "ActionOutput",
                        "OutputName": "Dictionary Value"
                    },
                    "WFSerializationType": "WFTextTokenAttachment"
                },
                "WFGetDictionaryValueType": "Value",
                "WFDictionaryKey": {
                    "Value": {
                        "string": "file",
                        "attachmentsByRange": {}
                    },
                    "WFSerializationType": "WFTextTokenString"
                },
                "UUID": u_fb_file
            }
        },
        # 17. Set Image URL from fallback
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
            "WFWorkflowActionParameters": {
                "WFInput": {
                    "Value": {
                        "OutputUUID": u_fb_file,
                        "Type": "ActionOutput",
                        "OutputName": "Dictionary Value"
                    },
                    "WFSerializationType": "WFTextTokenAttachment"
                },
                "WFVariableName": "Image URL",
                "UUID": u_fb_setvar
            }
        },
        # 18. Otherwise (random item is an image)
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.conditional",
            "WFWorkflowActionParameters": {
                "GroupingIdentifier": group_rand_is_video,
                "WFControlFlowMode": 1
            }
        },
        # 19. Get featured_image from random item
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.getvalueforkey",
            "WFWorkflowActionParameters": {
                "WFInput": {
                    "Value": {
                        "OutputUUID": u_rand_item,
                        "Type": "ActionOutput",
                        "OutputName": "Item from List"
                    },
                    "WFSerializationType": "WFTextTokenAttachment"
                },
                "WFGetDictionaryValueType": "Value",
                "WFDictionaryKey": {
                    "Value": {
                        "string": "featured_image",
                        "attachmentsByRange": {}
                    },
                    "WFSerializationType": "WFTextTokenString"
                },
                "UUID": u_rand_feat
            }
        },
        # 20. Get file from random item
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.getvalueforkey",
            "WFWorkflowActionParameters": {
                "WFInput": {
                    "Value": {
                        "OutputUUID": u_rand_feat,
                        "Type": "ActionOutput",
                        "OutputName": "Dictionary Value"
                    },
                    "WFSerializationType": "WFTextTokenAttachment"
                },
                "WFGetDictionaryValueType": "Value",
                "WFDictionaryKey": {
                    "Value": {
                        "string": "file",
                        "attachmentsByRange": {}
                    },
                    "WFSerializationType": "WFTextTokenString"
                },
                "UUID": u_rand_file
            }
        },
        # 21. Set Image URL from random item
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
            "WFWorkflowActionParameters": {
                "WFInput": {
                    "Value": {
                        "OutputUUID": u_rand_file,
                        "Type": "ActionOutput",
                        "OutputName": "Dictionary Value"
                    },
                    "WFSerializationType": "WFTextTokenAttachment"
                },
                "WFVariableName": "Image URL",
                "UUID": u_rand_setvar
            }
        },
        # 22. End If for random item video check
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.conditional",
            "WFWorkflowActionParameters": {
                "GroupingIdentifier": group_rand_is_video,
                "WFControlFlowMode": 2,
                "UUID": u_rand_endif
            }
        },
        # 23. Otherwise (Today is NOT a video)
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.conditional",
            "WFWorkflowActionParameters": {
                "GroupingIdentifier": group_is_video,
                "WFControlFlowMode": 1
            }
        },
        # 24. Get featured_image from today's item
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.getvalueforkey",
            "WFWorkflowActionParameters": {
                "WFInput": {
                    "Value": {
                        "OutputUUID": u_today_item,
                        "Type": "ActionOutput",
                        "OutputName": "Item from List"
                    },
                    "WFSerializationType": "WFTextTokenAttachment"
                },
                "WFGetDictionaryValueType": "Value",
                "WFDictionaryKey": {
                    "Value": {
                        "string": "featured_image",
                        "attachmentsByRange": {}
                    },
                    "WFSerializationType": "WFTextTokenString"
                },
                "UUID": u_today_feat
            }
        },
        # 25. Get file from today's item
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.getvalueforkey",
            "WFWorkflowActionParameters": {
                "WFInput": {
                    "Value": {
                        "OutputUUID": u_today_feat,
                        "Type": "ActionOutput",
                        "OutputName": "Dictionary Value"
                    },
                    "WFSerializationType": "WFTextTokenAttachment"
                },
                "WFGetDictionaryValueType": "Value",
                "WFDictionaryKey": {
                    "Value": {
                        "string": "file",
                        "attachmentsByRange": {}
                    },
                    "WFSerializationType": "WFTextTokenString"
                },
                "UUID": u_today_file
            }
        },
        # 26. Set Image URL from today's item
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
            "WFWorkflowActionParameters": {
                "WFInput": {
                    "Value": {
                        "OutputUUID": u_today_file,
                        "Type": "ActionOutput",
                        "OutputName": "Dictionary Value"
                    },
                    "WFSerializationType": "WFTextTokenAttachment"
                },
                "WFVariableName": "Image URL",
                "UUID": u_today_setvar
            }
        },
        # 27. End If for today video check
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.conditional",
            "WFWorkflowActionParameters": {
                "GroupingIdentifier": group_is_video,
                "WFControlFlowMode": 2,
                "UUID": u_today_endif
            }
        },
        # 28. Replace dynamicimage CDN with content/dam master URL
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.text.replace",
            "WFWorkflowActionParameters": {
                "WFInput": {
                    "Value": {
                        "string": "\ufffc",
                        "attachmentsByRange": {
                            "{0, 1}": {
                                "VariableName": "Image URL",
                                "Type": "Variable",
                                "Aggrandizements": [
                                    {
                                        "Type": "WFCoercionVariableAggrandizement",
                                        "CoercionItemClass": "WFStringContentItem"
                                    }
                                ]
                            }
                        }
                    },
                    "WFSerializationType": "WFTextTokenString"
                },
                "WFReplaceTextRegularExpression": True,
                "WFReplaceTextCaseSensitive": False,
                "WFReplaceTextFind": "^(https://assets\\.science\\.nasa\\.gov/)dynamicimage/assets/([^?#]+).*$",
                "WFReplaceTextReplace": "$1content/dam/$2",
                "UUID": u_replace
            }
        },
        # 29. Download master image
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.downloadurl",
            "WFWorkflowActionParameters": {
                "WFURL": {
                    "Value": {
                        "string": "\ufffc",
                        "attachmentsByRange": {
                            "{0, 1}": {
                                "OutputUUID": u_replace,
                                "Type": "ActionOutput",
                                "OutputName": "Updated Text"
                            }
                        }
                    },
                    "WFSerializationType": "WFTextTokenString"
                },
                "UUID": u_img_url
            }
        },
        # 30. Detect images
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.detect.images",
            "WFWorkflowActionParameters": {
                "WFInput": {
                    "Value": {
                        "OutputUUID": u_img_url,
                        "Type": "ActionOutput",
                        "OutputName": "Contents of URL"
                    },
                    "WFSerializationType": "WFTextTokenAttachment"
                },
                "UUID": u_detect
            }
        },
        # 31. If images does not have value
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.conditional",
            "WFWorkflowActionParameters": {
                "WFInput": {
                    "Type": "Variable",
                    "Variable": {
                        "Value": {
                            "OutputUUID": u_detect,
                            "Type": "ActionOutput",
                            "OutputName": "Images"
                        },
                        "WFSerializationType": "WFTextTokenAttachment"
                    }
                },
                "WFControlFlowMode": 0,
                "WFConditionalActionString": ".jpg",
                "GroupingIdentifier": group_img_valid,
                "WFCondition": 101
            }
        },
        # 32. Show notification on error
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.notification",
            "WFWorkflowActionParameters": {
                "WFNotificationActionBody": "There is no APOD today.",
                "UUID": u_notif,
                "WFNotificationActionSound": False,
                "WFNotificationActionTitle": "Error"
            }
        },
        # 33. Otherwise (image is valid)
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.conditional",
            "WFWorkflowActionParameters": {
                "GroupingIdentifier": group_img_valid,
                "WFControlFlowMode": 1
            }
        },
        # 34. Resize image
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.image.resize",
            "WFWorkflowActionParameters": {
                "WFImageResizeKey": "Size",
                "WFImageResizeHeight": "1440",
                "UUID": u_resize,
                "WFImage": {
                    "Value": {
                        "OutputUUID": u_detect,
                        "Type": "ActionOutput",
                        "OutputName": "Images"
                    },
                    "WFSerializationType": "WFTextTokenAttachment"
                },
                "WFImageResizeWidth": ""
            }
        },
        # 35. Set wallpaper
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.wallpaper.set",
            "WFWorkflowActionParameters": {
                "WFWallpaperShowPreview": False,
                "WFWallpaperSmartCrop": False,
                "WFWallpaperPerspectiveZoom": True,
                "UUID": u_set_wall,
                "WFSelectedPoster": {
                    "name": "Wallpaper 8",
                    "providerBundleIdentifier": "com.apple.PhotosUIPrivate.PhotosPosterProvider",
                    "UUID": "2DA00F60-7B8F-4466-BB42-148FEF696568"
                },
                "WFInput": {
                    "Value": {
                        "OutputUUID": u_resize,
                        "Type": "ActionOutput",
                        "OutputName": "Resized Image"
                    },
                    "WFSerializationType": "WFTextTokenAttachment"
                },
                "WFWallpaperLegibilityBlur": False
            }
        },
        # 36. End If
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.conditional",
            "WFWorkflowActionParameters": {
                "WFControlFlowMode": 2,
                "GroupingIdentifier": group_img_valid,
                "UUID": u_valid_endif
            }
        }
    ]

    wflow = {
        "WFWorkflowClientVersion": "5037.0.19",
        "WFWorkflowActions": actions,
        "WFWorkflowIcon": {"WFWorkflowIconStartColor": 255, "WFWorkflowIconGlyphNumber": 61509},
        "WFWorkflowInputContentItemClasses": [
            "WFAppStoreAppContentItem", "WFArticleContentItem", "WFContactContentItem",
            "WFDateContentItem", "WFEmailAddressContentItem", "WFFolderContentItem",
            "WFGenericFileContentItem", "WFImageContentItem", "WFiTunesProductContentItem",
            "WFLocationContentItem", "WFDCMapsLinkContentItem", "WFAVAssetContentItem",
            "WFPDFContentItem", "WFPhoneNumberContentItem", "WFRichTextContentItem",
            "WFSafariWebPageContentItem", "WFStringContentItem", "WFURLContentItem"
        ],
        "WFWorkflowImportQuestions": [],
        "WFWorkflowTypes": [],
        "WFQuickActionSurfaces": [],
        "WFWorkflowHasShortcutInputVariables": False,
        "WFWorkflowHasOutputFallback": False,
        "WFWorkflowOutputContentItemClasses": []
    }

    return actions, wflow

def main():
    actions, wflow = build_workflow()

    # 1. Write temporary wflow
    tmp_wflow = "/tmp/APOD_Wallpaper_clean.wflow"
    with open(tmp_wflow, "wb") as f:
        plistlib.dump(wflow, f)

    # 2. Sign shortcut into repo
    repo_shortcut = os.path.abspath("APOD_Wallpaper.shortcut")
    res = subprocess.run(["shortcuts", "sign", "--mode", "anyone", "-i", tmp_wflow, "-o", repo_shortcut], capture_output=True, text=True)
    if res.returncode != 0:
        print("Error signing shortcut:", res.stderr)
        return
    print(f"Signed shortcut written to {repo_shortcut} ({os.path.getsize(repo_shortcut)} bytes)")

    # 3. Update local Shortcuts.sqlite
    db_path = os.path.expanduser("~/Library/Shortcuts/Shortcuts.sqlite")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    actions_blob = plistlib.dumps(actions, fmt=plistlib.FMT_BINARY)
    c.execute("UPDATE ZSHORTCUTACTIONS SET ZDATA = ? WHERE Z_PK = 54", (actions_blob,))
    c.execute("UPDATE ZSHORTCUT SET ZACTIONCOUNT = ? WHERE Z_PK = 54", (len(actions),))
    conn.commit()
    conn.close()
    print(f"Updated local Shortcuts.sqlite with {len(actions)} actions.")

if __name__ == "__main__":
    main()
