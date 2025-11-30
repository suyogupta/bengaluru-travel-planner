import crypto from 'crypto';

const generateHash = (data: string) => {
  return crypto.createHash('sha256').update(data).digest('hex');
};

export { generateHash };
