#
# Copyright (c) 2024 The C++ Alliance, Inc. (https://cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/boostorg/website-v2
#

# import requests
#
# from django.conf import settings
#
#
# def get_link_preview_data(link):
#     """gets the link preview json response from LinkPreview api"""
#     api_url = "https://api.linkpreview.net"
#     api_key = settings.LINK_PREVIEW_API_KEY
#     target = link
#
#     # TODO: Add additional field `image_size` to help validate image https://docs.linkpreview.net/#image-processing-and-validation
#     response = requests.get(
#         api_url,
#         headers={'X-Linkpreview-Api-Key': api_key},
#         params={'q': target},
#     )
#     return response.json()
