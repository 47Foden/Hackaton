import { useState } from 'react';
import { StartScreen } from './screens/StartScreen';
import { OrderScreen } from './screens/OrderScreen';

export function App() {
  const [screen, setScreen] = useState<'start' | 'order'>('start');
  return screen === 'start'
    ? <StartScreen onStart={() => setScreen('order')} />
    : <OrderScreen onHome={() => setScreen('start')} />;
}
