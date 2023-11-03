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
