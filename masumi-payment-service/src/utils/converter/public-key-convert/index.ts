import { Ed25519PublicKey } from '@meshsdk/core-cst';
import { Cbor, CborNegInt, CborMap, CborBytes } from '@harmoniclabs/cbor';
import JSONBig from 'json-bigint';

export function getPublicKeyFromCoseKey(cbor: string): Ed25519PublicKey | null {
  const decodedCoseKey = Cbor.parse(cbor) as CborMap;
  const publicKeyEntry = decodedCoseKey.map.find((value) => {
    return (
      JSONBig.stringify(value.k) ===
      JSONBig.stringify(new CborNegInt(BigInt(-2)))
    );
  });

  if (publicKeyEntry) {
    const publicKeyBuffer = Buffer.from((publicKeyEntry.v as CborBytes).bytes);
    return Ed25519PublicKey.fromBytes(publicKeyBuffer);
  }

  return null;
}
