import requests
import sys
from time import sleep


# WARNING: This has not been tested on a real flight yet
def check_in(confirmation_number, first_name, last_name):
    info = {"first-name": first_name, "last-name": last_name}
    site = "mobile-air-operations/v1/mobile-air-operations/page/check-in/" + confirmation_number

    response = make_request("GET", site, info)
    print(response.json())

    site = "logging/v1/logging/mobile/log"
    reservation = make_request("POST", site, info)
    print(reservation.status_code)

def make_request(method, site, info):
    url = "https://mobile.southwest.com/api/" + site
    headers = get_headers()

    # In the case that your server and the Southwest server aren't in sync,
    # this requests multiple times for a better chance at success
    attempts = 0
    while True:
        if method == "POST":
            response = requests.post(url, headers=headers, json={"names": info})
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
    headers = {
        # "Host": "mobile.southwest.com",
        # "Content-Type": "application/json",
        # "Accept": "*/*",
        # "X-Dublriiu-A": "67-G-yArp-JTdU3KQNq2zGz-VNuVXC_NrqEnIe4_fCONrKlyCooeecbosbXdmTC-uV_UfV=3BZ05VUpihO44wsDESHiTgNU7IA9jOR1WJjbu_WGfJrwB62F6_CuWhkE3lA5_ymgqptw3ShFHtne3m5rS_hIgYIxQzQN-qxmP4YU_BDSuncfHRwj=lJaIbs8jbARRUcq1ov6juvqou2_m6S_QofTTqgUa_KlG7tt5yRTO9tqBC5r93Evh=NlqqD-ydtCvilwXSsE0w52-dCK9w-RWlcojnzr8i8WIe4DXY=Cr-b3f=lMyyqYp8N0M_42ZPbDyl1xCB8QS3Ig=KnB0vdvyy0BtqMgTnkCSswSG4zHZyKsIqkU76PNuiVS0qH7_AM7iW82oCafy-b36Gw=fG_SBxm9CRp0BHWcGJ3bCo81SG9EbiPeow93PrEQawYCmXp3p3n6HHk6tMDa2UnHIzW80kHYQ90N8WDRudlH6i0mWrJOtHh48nlhE8C3xEEy3ZEH1RnVeZnSXyVlSXabl_VXwnHAifWy-CWoIQtD60xKlp95P40Bj6==6Z9p4zNN3Ty6IZAZ5HdDdFlyqS8cl_vT2uzWyUnTMVtgiss4Gx4HjglFq5qSZQA2cKax4jw=sMV5a49CWwEhafmZIDkOxEFDaWHJppqSOyMVucFpPedCgsI5Mwm4-=jNCGTwmgRuowURRH-PZSdBbBqD-HMczCn=ZaigxgMmrAem=vBze96FABli3EDr1UN6-kqDnip1NrR-1u4BwMWu55NoT9gDt9KYim9CJ1vPBE7nKuBwuE7yVsoGBxag5wXuQfyDdqcJDpmES5ev2g8S2hlfuE6egF_eP72fRPqY1-Bf7y85Fdrka_GxBTA4tI92XYUkOJPuA7jxBiCkXre93k0ls7trSG=prC5_S7mlC3XFdOSF9y08QCTFcjB2M0IVTJe9q0RmYP8heNmtJWh=SN2CcpfuDYZizu4pT5QiJyAyARSrxjHzAMK56221hIlxxRsFbWxyUCEAjeBJJAJSFCEU-0puykegEkt3_VTdBmtfKKxwVwqsBZM88w9Afn-ldd6kF90a9sTCCtrGjNjEcF0zRZbIaHX3MqJP9gyeGkZ9fjXwjoxsm0-xbKQnl1EKEuqkQr4B=fPMg0tfSaIo9H2ZIkI4bPMFu7oSIDv1cohXQspTZG4awW9upsn-xOebklEDBaSdXrjav18zItlquexcEZXYHChl6Er-lbiD5nDNX25AK3Jj0Cj=_asWyaVAhBA_8xX-9tchM9PtXGZdyDvz=Sn3ygc0ub2SMHGtp3rQ5nBVbk7mCxjdR9uI7p71dHK2phF5Tl0ByKhDTpwBs8-kb6H_AmcOQ-=lwGdtCA4TbjCYURi47tvRk2PW9ha6zdMXf=EvMT12XSVNR-QxY5v7izelPk4dqTzUJnOM4N28Mue__gMAOFwnSuf3ydnTh2es=9J1eBz46QoPcT5RbzCYsXZXkBzVEx3ipCeDWkamYVjYWJoRbA8C3TP4GM-EHYhl2PJR0a=Ivi0MJKRX0QiO5noCeH3roy8UEU6y-mb7Riq3mGu8IUQulgJ_F1Jj5cCbaDcOnFjP-eTMsIA9dWgkRyskBQTZeG3j2xBaHU07yjUAeTNTzOhUTx1a3-5-CqSnc2xn5c_4AT5Wo-UAtcDrlTmt8f4hkOQdP4jOnD7SC_WZ2q-SPa9FnyNAAPNXUn_3KnTwJFho2u7NF3egQkiq0wb4vavFIpRaBg4dT6i2gJNZ-0MsaG=KiVIsI8tW3ai4pr41cDjiPDsmQAtQXTcv2V4aVTuhyA5hU7E70tX7FPBy8ANjxaYg-Dri2h0m1yx2i45topTgfVkYRmYE9ugtxd9_iTlAsbBrujO5Gr-ljlbz_XW5QfcmOEid=PXy3BxQC9tPquWB2EHRPxE8=J6HJ3Vcby053_qiIbmff3-MS8Vy8JGYy=9fWSRJ1jzwHmP1DZTwN4Gw92jx07wiC34sFz_KpTw5-CGPdhrQfxdyqOIHbmlZYmJxye88GISaAV_fCGt0UBthzIm=Bv2r=QOwa2qkyKSZSWx9FQWjJNyqceAofJR4x-iyy35VTmVCy5E6q1_9ZMutvWrJkmYuNvgQFPda0bKJUKCb-5O4_aa89khNlcDASY_TVb7R3BEQ2YQ4rMxyYC69_Wrs50v5YKJn_1NPX384=m39G=S2B24dat3JWno78uXpMs5Wh42COyfGjk3oOn86IP1Jd6aXqYjNIrf99nWwGRNJ1m69NBcnNUh3xCE-uCw=cdrZ-=K_pff9HEOH=j6QNepnZ0grj3Yn=OVi1J1ubUnxddFr9owJ-h_OWNzue5153nHM=JXE4wdX-OgkHAohc1fXG83B=1yH5vXVTpPIXYCOQtWdnWBdMZp-brnWPmJeJQ_ZrkFNXyug8ZPVJZlXP7kxfZg2E26TUwu0l7xtePO77VKgTUTycitNi4nnnhbsFF6IRpWaYew1ACs_QRPE59Cp6dZ4J8F28vqG83XxXO5baZc7oQhsKb1FDlixE3kBrriSZa73GWR1s4XxR8NdyNtUTiOVmCSswTMMczKy1-sTO6WqGngeUI2XtApfiy3Mmq54R28f6bkxEp1rzYCBcP3p4nDd9vqveaEtJ5m81U7WsNC4D5Wa3W1bj=oeF8Rx4GBFBn=VfFMTutny=nci5EK1obn819uy1JyF-o-v_eRhqjJF98eu5d-E7as9m6nHG1wqrHU6OJfa7kCBG4CpTjpgiTY3_8MU=c8CS8JSQ5Br3oW7fBb4rdmQTEnXqK-QnR6MOg_MAl5Ik_6_VDJgCFCsCnbpNbbSb_09n4jrjasK582SJqolrImGrKdr8crYCOo6m_7Hea_gdD2R-bdO97BIEyPUrn=OT4KHW43-QxOzXfj2aC5HZpS0lMf_dECbd_jg0nXBOqScO3gGjVJEpfO9f1aAsTBPuUCk0Dfl-M90fTTsunbNIqsFnyRK=qCt8E4B-=tpfwMdFxoo3W2p0pSXi3WyTokifZuYrSA5zy7S-pVXAGsoNsxoKx7pIaBCONOEsm_ueapJuk1lJbXs9osXYmc2sc70ahK6f8OA0aaVhTnB7xduX5WJt_amiQmroECFhQHhNk=QkpM=EGB1k-N-WbHo4_O_VfxoRPYbG5-2B7rBza1SCbJh5iPdF6IZVOBibxxXDPsxzCASn-wj-W8pkEb-0X9_BEw8qr5xIXtVNzak-0xrUBvlgtAR-QSOGDnaG9J-SsBIJpU=t7nOWjQX6QM4JN33wxoXCpobgEK8JQqKxtOkFN_7s8-sqIBsC8bTlH_ubx2dhfwYJEU46-nwFNQA1B=VMCCggtSzPcRR2aoxOB5XeZX5Wd88Xxq--qVTg1deQPCbPs-hOKqexP58yhBvRnJrA2XWBHfh34IppYxk_VfCSUhYEDGwVO4APzP9DbJSkZYYniOwoOxKKg-=naN51gYR84o8VrkwsKfdlYKhpc9=VG2OAu4OIKm_oOUtAHJR2YW1qIh1WcMQ5dv59DjlDS4=OeerMRc69NtRipMOzX8KdpzZ5vfVhuW33CzeKC4l4muoCIjeGR78WiPVoRl6cTglnfPVSnzqf9-zN6vSD2MwKnEF=30OnxmWHaSmCaOXnUR7edSjoRHAKCb47OYvTmCVUXwgpYe4Z4gankSzRUW65yGkBf0OnEs4cU=piVlxZog2IOQYsxmZwqaj1PBqDyPPS4FecHG0jVK55ux_89dRsiBIIS3IkgMkl_okHxX=DcfNClyoct=SIcurpqUMxdYmhgH3RWUiAQJw2WySrqogX1b8Yr=K4qOus83_Qq-svZHuxvJaPHn1ue_9DAFF8ymxpg-8mmwNAMVNxmVN_WKAWFoOSStH5kx9cPMpmefPeUO3uVihxewk3PEA9WkQDDxkzjTNhQxMMAB9h3RIO5FefWb7ApH1l5vkjCGWBuUsy_4MqGinEN-XQ1py_-I8KGMWf-CKr0QNoJHa_mmaScyVwBUsNe=q=NizWha6Q8u-5-mekbCib-hjMXlU2b727t7lNT2503gRqS2I3d3_zkqBMCmfymhIthEjmgi-_K9rX2HXg3lyFKiT=zl4YfweZNghnSk37QZaHHPjJt=D-TWZQUzhoOu-rslxjQe63ecxG1vRVoxTzsjnRfFjjz17OsrQDPFwA6WR3=ebRX4kiBXMECvvUKbwXJlQZ24CXAj3YZlG4NUTThuU4l3b6DGq-7zh6J0k_zC_R_sj2FfHTIDT=zs7bGyK--ub8qZ81GKOZDKiBMF4tRT3VsfYWZ4dhygVJrQtW7cGVqYAhUfE8B8ze66z0P_1EpRoCirDwVWtKxhY5FMGSKGVVz9onR_Y1_cC",
        # "X-Dublriiu-B": "-1ffcfg",
        # "X-Dublriiu-Z": "q",
        # "X-Dublriiu-C": "AEAteQV8AQAAaB-AgCKkzru4WUxxgQ9jW6TTnnCB2rYSRz7tuuTZ5r2ET6WBc",
        "X-Api-Key": api_key,
        "X-Channel-Id": "IOS",
        # "X-Dublriiu-D": "ABYQoAuABKgAhACAQYAQwAKIAIEwBOTZ5r2ET6WB_____80ML3YAI0iMUx-h8qVZxesN6NpleA",
        "X-User-Experience-Id": "3CDA348B-463A-4861-9400-F77362B172AC",
        # "EE30zvQLWf-f": "A1RPfQV8AQAAnQSKLiRZ5UODiX_Jrw2Sv3ctFgBhowKAb0HYZ5RdGm5mxnGTAaLN0g0X2gAX5qEO8YLqosIO8Q==",
        # "User-Agent": "Southwest/8.9.0 CFNetwork/1240.0.4 Darwin/20.6.0"
    }

    return headers
