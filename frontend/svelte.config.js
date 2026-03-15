import adapterNode from '@sveltejs/adapter-node';
import adapterVercel from '@sveltejs/adapter-vercel';

const config = {
  kit: {
    adapter: process.env.VERCEL ? adapterVercel() : adapterNode()
  }
};

export default config;
