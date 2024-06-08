import json
import logging
import os
import re

import requests

a_nosine = "\xC4\x85".decode("utf-8")
ch = "\xC4\x8D".decode("utf-8")
e_nosine = "\xC4\x99".decode("utf-8")
eh = "\xC4\x97".decode("utf-8")
i_nosine = "\xC4\xAF".decode("utf-8")
sh = "\xC5\xA1".decode("utf-8")
u_nosine = "\xC5\xB3".decode("utf-8")
u_ilgoji = "\xC5\xAB".decode("utf-8")
zh = "\xC5\xBE".decode("utf-8")

qou = "\xe2\x80\x9e".decode("utf-8")
qcu = "\xe2\x80\x9c".decode("utf-8")

logger = logging.getLogger(__name__)


def change_phonemes(hyp):
    logger.debug("Call change_phonemes: %s", hyp)
    wr_al = hyp.get('word-alignment', -1)
    ph_al = hyp.get('phone-alignment', -1)
    if wr_al != -1 and ph_al != -1:
        # print 'AAA'
        ph_last_inx = 0
        for wr_entry in wr_al:
            if re.search(r'^_[A-Z]+_$|^<unk>$', wr_entry['word']):
                wr_beg = wr_entry['start']
                wr_end = wr_entry['start'] + wr_entry['length']
                ph_beg_inx = -1
                ph_end_inx = -1
                # print str(wr_beg) + ' ' + str(wr_end)
                # print 'ph_last_inx = '+str(ph_last_inx)
                i = ph_last_inx
                while i < len(ph_al):
                    ph_beg = ph_al[i]['start']
                    ph_end = ph_al[i]['start'] + ph_al[i]['length']
                    # print ' P' + str(ph_beg) + ' ' + str(ph_end)
                    if ph_beg == wr_beg:
                        ph_beg_inx = i  # [
                    elif ph_end >= wr_end:
                        ph_end_inx = i  # ]
                        break
                    i += 1
                ph_last_inx = i
                if ph_beg_inx > 0 and ph_end_inx > 0:  # phone sequence that matches the word was found
                    # the last phone isnot '_E' terminated
                    if re.search(r'_E$', ph_al[ph_end_inx]['phone']) == None:
                        if (ph_end_inx > ph_beg_inx and re.search(r'_E$', ph_al[ph_end_inx - 1]['phone']) != None):
                            ph_end_inx -= 1
                        if (ph_end_inx + 1 < len(ph_al) and re.search(r'_E$', ph_al[ph_end_inx + 1]['phone']) != None):
                            ph_end_inx += 1
                    ph_str = " ".join(ph_entry['phone'] for ph_entry in ph_al[ph_beg_inx:ph_end_inx + 1])
                    ph_str = re.sub(r'_[BESI]{1,2}(?= |$)', '', ph_str)  # delete _I, _B

                    # phones2letters2 calls service
                    wr_entry['word'] = phones2word_service(ph_str)
        return " ".join(wr_entry['word'] for wr_entry in wr_al), True
    return None, False


# phoneme-to-grapheme rules
# phoneme string is space-separated but without positional extensions _B _E _I _S
# to be included into 'worker.py'

def phones2word_rules_backoff(ph_str):
    ph_str = re.sub(r'(?<= [aeo] v\' i tS\' )"e:(?= m. s$)', 'ia', ph_str)  # stankeviciams
    ph_str = re.sub(r'(?<= ^[aeo]: v\' i tS\' )eu', 'iau', ph_str)  # stankeviciaus

    ph_str = re.sub(r'tS', ch, ph_str)
    ph_str = re.sub(r'Z', zh, ph_str)
    ph_str = re.sub(r'S', sh, ph_str)
    ph_str = re.sub(r'E', eh, ph_str)
    ph_str = re.sub(r'ts', 'c', ph_str)
    ph_str = re.sub(r'G', 'h', ph_str)
    ph_str = re.sub(r'x', 'ch', ph_str)
    ph_str = re.sub(r'N', 'n', ph_str)

    ph_str = re.sub(r'(?<=j)( [\^\"]?)i([ou])', r'\1\2', ph_str)

    ph_str = re.sub(r'(?<= )a: j i:$', a_nosine + ' j ' + i_nosine, ph_str)  # aji
    ph_str = re.sub(r'(?<= )a: j e:$', a_nosine + ' j ' + a_nosine, ph_str)  # aja
    ph_str = re.sub(r'(?<= )i: j i:$', i_nosine + ' j ' + i_nosine, ph_str)  # iji
    ph_str = re.sub(r'(?<= )u: j i:$', u_nosine + ' j ' + i_nosine, ph_str)  # uji
    ph_str = re.sub(r'( [\^\"]?i?)u: j u:$', r'\1' + u_nosine + ' j ' + u_nosine, ph_str)  # uju

    ph_str = re.sub(r'[\^\"]i:$', 'y', ph_str)
    ph_str = re.sub(r'(?<= )i:$', i_nosine, ph_str)
    ph_str = re.sub(r'(^|^[nbt]\' e |^[nt]\' e b\' e)[\^\"]?i:', r'\1' + i_nosine, ph_str)
    ph_str = re.sub(r'i:', 'y', ph_str)

    ph_str = re.sub(r'(?<= )[\^]?a:$', a_nosine, ph_str)
    ph_str = re.sub(r'(?<= )[\^]?a:(?= s$| s\' i$)', a_nosine, ph_str)
    ph_str = re.sub(r'(?<= )e:(?=$| s$| s\' i$| s\' i s$)', e_nosine, ph_str)

    ph_str = re.sub(r'( [\^]?i?)u:$', r'\1' + u_nosine, ph_str)
    ph_str = re.sub(r'((?:^| )[\^\"]?i?)u:(?= )', r'\1' + u_ilgoji, ph_str)

    ph_str = re.sub(r'[\.:\'\"^ ]', '', ph_str)  # delete single quote
    return ph_str


# to be included into 'worker.py'


## http://127.0.0.1:3000/phones2word
__env_name = 'PHONES2WORD_SERVER_URL'
__phones2word_server = os.getenv(__env_name)

if not __phones2word_server:
    logger.warning("No env %s", __env_name)


def phones2word_service(ph_str):
    if __phones2word_server:
        headers = {'Content-Type': 'application/json; charset=utf-8'}
        data = {'phones': ph_str}
        try:
            logger.debug("Call phones2word_server, url: %s", __phones2word_server)
            r = requests.get(__phones2word_server, headers=headers, json=data, timeout=10)
            r.raise_for_status()
            parsed_response = json.loads(r.text)
            return parsed_response['word']
        except Exception as e:
            logger.error("Phones2word service error: %s", str(e))

    return phones2word_rules_backoff(ph_str)
