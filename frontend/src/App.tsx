import { useState } from 'react';
import { StartScreen } from './screens/StartScreen';
import { OrderScreen } from './screens/OrderScreen';

export function App() {
  const [screen, setScreen] = useState<'start' | 'order'>('start');
  // The order screen is mounted only for the lifetime of one order session.
  return screen === 'start'
    ? <StartScreen onStart={() => setScreen('order')} />
    : <OrderScreen onHome={() => setScreen('start')} />;
}
