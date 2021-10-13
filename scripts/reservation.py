import requests
import sys
from time import sleep


# WARNING: This has not been tested on a real flight yet
def check_in(confirmation_number, first_name, last_name):
    info = {"first-name": first_name, "last-name": last_name}
    site = "mobile-air-operations/v1/mobile-air-operations/page/check-in/" + confirmation_number

    response = make_request("GET", site, info)

    info = response['checkInViewReservationPage']['_links']['checkIn']['body']
    site = "mobile-air-operations/v1/mobile-air-operations/page/check-in"

    reservation = make_request("POST", site, info)
    return reservation['checkInConfirmationPage']

def make_request(method, site, info):
    url = "https://mobile.southwest.com/api/" + site
    headers = get_headers()

    # In the case that your server and the Southwest server aren't in sync,
    # this requests multiple times for a better chance at success
    attempts = 0
    while True:
        if method == "POST":
            response = requests.post(url, headers=headers, json=info)
        elif method == "GET":
            response = requests.get(url, headers=headers, params=info)
        else:
            print("\033[91mError: Method {} not known\033[0m".format(method))
            return

        if response.status_code == 200:
            return response.json()

        if attempts > 20:
            break

        attempts += 1
        sleep(0.5)

    print("Failed to retrieve reservation. Reason: " + response.reason)
    sys.exit()

def get_headers():
    response = requests.get("https://mobile.southwest.com/js/config.js")

    if response.status_code != 200:
        print("\033[91mFailed to retrieve headers. Exiting...\033[0m")
        sys.exit()

    keys = response.text.split("IOS_API_KEY")[1]
    api_key = keys[1:keys.index(',')].strip('"')

    # I'm keeping these headers here because I am not sure which ones I will need to successfully check in
    # These seem to be the only three you need, but I'm not sure how "X-Dublriiu-E" is generated
    headers = {
        #"Host": "mobile.southwest.com",
        #"Content-Type": "application/json",
        #"Accept": "*/*",
        #"X-Dublriiu-A": "wCO_O-GlXGHMUCPHAC_5i_7MlFJmv_yM5AiKVTVxjH7y9-K4wXU7OtGyOgA_ntQD8bKpKB1uiW-lRyWrzGT5lz7_6quDoUwo3YtymLP3t1piy1fGN2W2l0ktfI7sXy79AAYnX_I1cP-UY6O1c_sZI8CCKI1rxq0lBmHHsOhyfG8ofmyC8A2ccayC7r9nkJ5KFEHw6lo5IaH6YvzaiSKcblFcvKRE1tt=Y_NfJARdiPXRox5v7d4n67vxxlZJEOcE02gn7_Pz1yCYLj3h3-bVLn1HVVY4sl4BG3C8Itbi4McvMjxOTn-o-rVlxcldthqFNj7-IxJHsv=KjrQV1bxv3aEOKNEhPrdpfmnkxXy8MxF5UYQs8NwQplzKhdz2XSPE0H5xMgcY29lhKGAMhQ7rGwU-TTWF9-8_cpSPUchAb61u1CBIF25M56rIIdHx3CFug-a8R3atcJlUYyKRiZdbHPaZG4Bc=xppYImw-NntbUtn1IvX_2o_hIRwrGzgCIrBbAlM09gUK8q26VzAlUuU-8ZGuEguLQvqR=OFIfS0Wr8oy-pHDxgT9tCVJ8mdsJ23LcfTF1gQuDu1GzyBS-opp2-jC9TjtYYURMzQm=a8sf9z=kZhDLicQ2x4fhB2EkHwJsZL7T0Y4DR-KCUADXUiSul1XY_uL0vjV0UW=tQC0P=QAw4hZ6gmOs_=h-ASPIt5z-ocA_1G-cP0-2GMzUp=RLcbZ12wBpHk8ZIwmMPn8xg=CofaNv6lrMalFGTr5sWJ3ip=i9bk3fgVyBtsWsvnAWnPgQnBzSc9mSy7cLi0Ym7HTitYbnDSNSjOjnXTHuLs6XUFPrCi-0qWHmyadAS56WzciaTRq-iDY1D56y2XtfkZ6p=cLfiu5yd6PhCT6zj_5V3aP__NdqOXwCUEDN7IF0G=TJprdQJBkoRd4cuyis8DdHAwx3xw-WqU_IUTK==YbGAEY5yrARlrvPFG-UjhEjNLzW6vbsHpY_mU7W_-ExqApMAGodO7-ilh93H1QqRo5AzZACv1uzs6LpgFTU12xrh9tN=QV49VnfjmjzbQ5HEzTSEk-FldVW5B8vLo328VViMuzFPkkGQ3224y4ZIBuotaZ0YJcqUo4ftQpCxd4zTnx6LY8RJ5SfWwON7bdUQNjOulTOvViwPtdyY9zH0X-zA1GZR-UBLS844iGqUrKz=X-ruBBZc91OqI7MS10TqvaPGn3hC6qxSiVZA3Ryp6Xjr1ZzC9kSnYxptSpsqw5T_KFZxpczWWhks-F-PyPBg44N7xcWBbJxzymcI802LmJCcR5mrduQXMYy6ZtTPfjm0I4CakLb66Sf7Odh0Y_po-avdmjuNoNgGBUImABY3huNrf1d2rj1oVfasPyDXfVv8FVi7RsAnZ27Oy8nMbpZUV2BvqqQ=60hnOIHl2GMIWBS=wHIRm0obX-pC5DpInW4K5Q76vitHf-7P=BH8Fsp0Xh1wKQnNBAw5Tk=SL_d3ffPsFraADP96QkIzXhKXxfSqTfPn=9h=01d9yck-LwLd1L_MX8lxSi11E3xYorEGFnly65=dCJrHlT1EGQxvfJ81YBst7sH9ng5HCU67ISWNR96w5jEnKmiMKxmdtkGi43RrnXobwhK1DiToq7F1gxCJwnKDFjxE-hg0-x7obu3TkI1xMuEcV7GDlll1yduuPsPLW_zr_6s=_ti=V1n815=EdH4j7sEKAAPCGXMp68xHX6LVOGfrzZxUG01QDMIBvourCHXqaRC4_DY1otzK4zuGMCEjpzu-fFfwJPR-DpMNGGERBJa=mSj31AUI1FuFZZKcjYCLkh4uNEOxp87PNHMnptElaUjZFiuA08IEc6xKSki33ygLlZu4aYuH_fn=cyNtirMxSVDTVcvPbybFE2K8-u1dD4iIXdGNOgrOnDJ-gNb4-htdrlA2ra7C4OPrB46WpV9xE0OR_RobyJM-pM5=cHg1U-6HIuRgbZfKfdtBC3Ir8Bdpg9Wy0ysRMu-cQGr3xs8Th1nSynu18Vwx_=iFROkB14brKm0VyClQJDAraJ7XVJB0PJjU5AXDcFgiz-xqoTuFiJ_8rJs9ZH2BIVCz_HPpcZu3iC-iZJ8PaQvUQaydf-1l6y3FS1yA9RTNpOZC95Ai__1TNHGXO_PRY7fJvm7hbdWVYSzwVfMQ5shgLqSFRchHjmnaHgX9_4aos9cOVbdsohJGvBC5cRCyaZaOuXEq5bFzC8azIGSC7nE2w=uzcb=m1U5phddYisBYc_=JYwbbUjfo1Xrn9QZVI8=UATEsZ3rOAKOIKvNY-ObKcjhtDsTNcMo0TQScnqFA_bAYWtVbdw0bnw_1P2OCd9_hmF9-gXfozrYbnRZNcqa44iKVFbuXP6Z5=kPHZZ9YDnPowh2VWj_pWtP0Xw-6o3O2T4Y1trsoGDyhqTXJEYAZ8L7Y4t3TCBMpBNxPgPow57pYGEhJCT-MLxOAWmU5wZ-6DRPkaVF-6KFpp6AGSwVKAiu2nG5otngraPiW9HFS_frVUUk1MQhpyV9Q8pL=VxF7RKYi3PSGiioLK33Gay8LkaUgn_4dpBtz20jYsxrorIKt=4Na8=FPXsDR-XVWRRwR8C28LINTl3h2yPzcpKKME6LR9w4OO5q6NKU-lFDR_tOHvD1OmPPcN3JH9s3Vwg4Lz-FmKHU0IGCoG7pzv9c13BcuqiSu60PqvGaw2gwnFsFAwEHI1vYNO=6lfNo-hUBMxk0TEuOyvacB-VHw0nWbGGdZZaK=jNmv3FmA-mczB2diNhfCrvVoTX9KZ0XJz3v5lU2TnPSEGqrwWDthkJCbhqxSW6jMuQ-1LmGo6ZJfpXV=nAadqfhnpKN10faNaQDiAl2DkOHTLzKYynOZq2=H-WrIh83if4x0RcxA3DWS1u_Z_zAlF3DqSH8an2RJzt1M9lE9ofjXKYs8Up_BVKsBzCQcG72UhVtJ25fUCpZUaiF6X8hsK8U27_9N=r-9n8DWMlwzPaRfB5Fid-8FpnT6n7jda55aPQFAKNjyOv_oJzFTvRabj6Ek6b24Fdgsv8_ITP7CFPPhutNgmz4Wv1EcgHZuOxWJmRKKH90AXcWlUzBZHj=fc2ARPpdFs8uAKOC2WE_FRxdDpvBqsLURJBFgJIA=UGFW0WAYMU0tAn65B4JfwRxa0sbSL8o8tIUwxRHIuUUi5DNvMiDHOph275qC4-_LbKz6__3p77D6c699Qspk3EbyGxoTRjpCBAQ9CTwfdu_g2AtrRiSZVY_ldkiok9zkVYNkancgu1OZ00m0svBdyTVhq8Zxb9-EYw51jLAEQxX_TChMTcsooj4Aq=6xYnKA2_lqEEYOmS7tyHokyaaA0CTXc=VQfJBLz3PCEMv8pgrxtdnLImDgB_XJt25T9g92WCvypXVl3opu7kMbGG_7oT05Jpdr4q5hIlRu-OWnWk5M7SwyO2vqMGrN2D=d10R6QBjzRyMqplZL=0gbNYLWu0tV79169yhGWMmGibXEjlbxWFc2QDxRLvw1MA4UERZnoEH=mplnYVluyw7=4SAz=SzhEO-TV9orRD1Qv2hjaXNPHJ-rMiEouwG2bCP84bqhgOogiBUh5oknqJF_sV4h-vkaVPrhzM7Nw7j15RzPhS6=TRFJIHBSwJsm4gI4NnoZTTbEjV75Y2XnvCnqUQ2pNNBGfats_hLxJli45B-E2xDwAZWpTTNos_D3tG8nwD0UEysvSAgk-CBUtTt30hFuQznB-qhuDUuHCJi4mXhuCXAMAkkra9ONxtDkltaE1oCoTSZx-kE3Mb1hiCJENl5iR43ifMINC48riWnJlRYopGO9hscchKOynUcIu4FJVgK2pzpusAUOfSFMy9Sldo_f47mRWlgF5q4mYw98Mky3vvZ63rmXVSZt5EY1oBWWHcO1Lwy5o7ZDcy4n65QD9iVOdoS7CEk5gd7zHBrTV9rP1Vc7HDkvyqOyp0nrj7FJPdhGJzzivWrF28NKyLqI-ayzQjrA1nXuctofBqTPQ54ZnCVcT1tMCvJnLzg9792LiqdoDhlNqyj3BZ8cGq5Qf3-fRYChZK6RVBBXrfutlPF9dnkNMc3EmZwHEq7LYC0rmwDJRT3=D2YxWb6_GQgW0fnWmlVDrSiODfIp=1Gq0y3ZKd4dS9b5IEqE8Iy=uB7E6dNTYSSI8u_TA4fb6oaf8Yf_lmGCX=2TtyAXKUbGoDABSX7rdw8nF5Dl_3VLCid50MQ1G8laUIRMi4R4YRKv7i_r9Xq7fsCtwHzp6dXG4GItGmyicFtybtULfdoKUg6fOGp2tWZ3hfPb2LcaJ3wuAzJ8LCCkuLJcJ7LrBgM_hhpoLir___q1=dg7v7SHXsHvBYY9V2FxO",
        #"X-Dublriiu-B": "iosojp",
        #"X-Dublriiu-Z": "q",
        #"X-Dublriiu-C": "AAB7F3d8AQAAQoFVi2flsKvQ4dgfDYtBcZB7BFi66YTonqhKFLQMY-7KrgO9",
        "X-Api-Key": api_key,
        "X-Channel-Id": "IOS",
        #"X-Dublriiu-D": "ABYQoAuABKgAhACAQYAQwAKIAIEwBLQMY-7KrgO9_____80ML3YAQ6Ec99umwO_0fXUMF7hKMg",
        "X-Dublriiu-E": "b;te0SxOLv_9qudcUVKPg7EdF32KlnmBp1PWmX-8CiICpTl9jiKcrWPqsFDsv3zCNg-WumEuy_kb7U5enPyMWtaHw05vqBFnihUpE_way0AHLP_wY4gsiIy4f2qsOyQN-nsYLEjNh-iAek1cB-mNxIksljZIj-TGaYRvEHR2mDYPwetU3UT7l1YWpJeoTxxUhsY4yBqDcbk0U3ZOiKN_4MerkGU7Nz_rB6eyCslaaKahF0ptgSoqVQHR8werDFAwgRURRMoaRprYjV04MeISh4VtXozJjIL886f3RI3YZZ8IdTxoiTwsDZrhCIOZhJk2Y7EaI-CmrbrCHW0shhtsBDiFzkKXD7huXRJl0YJ5TjxyytPtfbTBjo36MfnA_t8nPR00K_joUlHbicYFhL2FdBb0z1icy9hVpNyzHuIoPaNQFk7wTBlrG-Nn48nCcN2uWS1Mtf6ABVc3bCk6A_MxrKDVyM0InWTsed4uCrNP03wKq0sW-ov5oqpiU2uVHwg5g61-rZsPY_HXJ-bKNjAwtiXAFyCs4nWJyC5y195L_70LI1ta5oRjlR4UFOk2jMgVCDtv5bmwoz13Bf_Jmp4R5rM3sj7PssP5PmSVLvyvf3rBPe5dxF2O1egESYrWX5COTMNQXaqDvFpFX-ivVQSSb6Fz3CZlZOmffvM_slyhRD1fa5IwnOn3Dp92cqHaoFavdf_q-DJnQDhPq12lorKSXTf-yZk0PCrqvlbpUWNPDLgiONZbBPOaN7KRz5Ukk09a7tBlhZVVqTfG-bFbnMZKKF2JwsHdRNPZu7W_vnDEpkd1_-3gQixYMwaJuSZWSBRYirWAOlIf41sevj6GT9ghhJScQ8nnVxVoLeM2HZSdMAyuDmI9DUOuksbGuuSRS2i_vDKuFYJjMvryV3zaQM0scI8uHcHT8ECITqT8_RzJACuIQ2uCcRPKj2;Hv7A5SRaRGnlbBSdFDpNeVL9ZgsQnAh2xopCGZs4HNA=",
        #"X-User-Experience-Id": "AA0EC380-4A6E-4F32-9045-42FABD316952",
        #"X-Dublriiu-F": "Ayz4F3d8AQAA9V54NqJC6nystxeWgfHybpqrsbF2l5x_l2EzScixK_pWWiatAaLN0g0X2gAXCT8O8YLqosIO8Q==",
        #"User-Agent": "Southwest/8.10.0 CFNetwork/1240.0.4 Darwin/20.6.0"
    }

    return headers
