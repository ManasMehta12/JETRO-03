import type {Metadata} from 'next';
import './globals.css';
export const metadata:Metadata={title:'Takumi · Technical Viva',description:'A live technical interview grounded in your approved knowledge release.'};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en"><body>{children}</body></html>}
