from Crypto.PublicKey import RSA
import base64

def pretty_time_delta(seconds):
    sign_string = '-' if seconds < 0 else ''
    seconds = abs(int(seconds))
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    if days > 0:
        return '%s%dd%dh%dm%ds' % (sign_string, days, hours, minutes, seconds)
    elif hours > 0:
        return '%s%dh%dm%ds' % (sign_string, hours, minutes, seconds)
    elif minutes > 0:
        return '%s%dm%ds' % (sign_string, minutes, seconds)
    else:
        return '%s%ds' % (sign_string, seconds)


class QueueIDs(object):

    HASH_PRIVATE_KEY_STRING = """-----BEGIN RSA PRIVATE KEY-----
MIICXQIBAAKBgQDpj++suK3vm2vodW5ZlTKf+cFPo8oksszHJrMeMHvHSD1wcWX7
QJG/0mE1UwL+B1I2T3I+ElDw5bn6Cjb8LkTIVDqq/IMhV60l+0q7E7KHI0+BoWZV
faYzaIa9QymGf/XfOpCW8zuz0nbQQhQQRNuSABffpAlbxPPhynpCHNdNdwIDAQAB
AoGBAOCted4pegj49gEUlibPA3gpBfDamuZaqesaK0xrT2cQ8ylrrLLaFlr0wlZN
mJ9N46QjIL7dV8ek9ha2JNbKm5ZT1PESObTlKwtgj39yZV0qmPPxOxvDVQ91xPwv
eGetI+sb4qR5jwKgBZvM1EgC0PcsCNRwnYqo0xhM+QQRb7phAkEA/R2YTGJXt1tc
HhlxIqlqjPeCWH5Evu/mh9rzISxDwwH9Jx6pSnxJK6xUrkkboUphlhqe2A3cYTvz
cMaI8AuhcwJBAOw5TIwwKB05uyIyHf9f4azpkcz2gEXtuZxJrRr4V7egcZi5krdF
TcasnP6nFqeXYr7wLQYO2HRYA4fPO+80Uu0CQQCRdxCv1VTT641lPvnmEbdKjHQ8
p1Sa5wR1zz8rMWVADUSP1u8z/3mNv9xqzVkzuKucuG/ReyXMO8gMaA0K56RBAkAb
6pWaR6Kl+Ymc+/FBmdIwvhWl9Eeqe/KgfrB/bHPpVoO2OdAV6pHLdeDD03lA6woX
aIjZm22HKlOYfCwoE7XtAkBs8B2ggrpa7gxBaVtJr4ZeFbtp6oldk1/zcfvIOcqi
VZUJiCaX2YxPG8QawZAptKXrYcbrWI3gb71NGa/+JyZQ
-----END RSA PRIVATE KEY-----"""

    HASH_PRIVATE_KEY = RSA.importKey(HASH_PRIVATE_KEY_STRING)
    HASH_KEY_PAIR = RSA.construct((HASH_PRIVATE_KEY.n, HASH_PRIVATE_KEY.e, HASH_PRIVATE_KEY.d, HASH_PRIVATE_KEY.p,
                                      HASH_PRIVATE_KEY.q))
    HASH_PUBLIC_KEY = HASH_KEY_PAIR.publickey()
    HASH_SIZE = 32

    @classmethod
    def decrypt(clazz, encrypted_id):
        return clazz.HASH_PRIVATE_KEY.decrypt(encrypted_id.decode("hex"))

    @classmethod
    def encrypt(clazz, id):
        return clazz.HASH_PUBLIC_KEY.encrypt(id.encode('utf8'), clazz.HASH_SIZE)[0].encode("hex")
